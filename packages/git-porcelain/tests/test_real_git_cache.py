"""RealRepo's memo and snapshot skip, counted by the processes it starts (``observer``).

Real git, real temp repositories: what a memo may skip is only known against the binary. The rule behind every
test: a skipped process must never turn into a stale answer, so each "remembered" test is paired with the change
that must make it ask git again.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import git_porcelain as porcelain
from git_porcelain import GitReadFailure, GitUnavailable, Identity, MissingRevision, NotFastForward, RealRepo, RealWorktree, Sha
from git_porcelain.real_done import Done
from git_porcelain.testing import apply_hermetic_env
from git_porcelain.testing import git as run

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

_ME = Identity("Cache Author", "author@example.invalid")
_REMOTE_OPERATIONS = [
    "push",
    "push_known",
    "push_refspecs",
    "push_request",
    "push_default",
    "push_lease",
    "lfs_push",
    "fetch",
    "sync",
    "delete_remote_at",
    "ls_remote",
]


class Rig:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.calls: list[tuple[str, ...]] = []
        origin = self.root / "o.git"
        run(self.root, "init", "-q", "--bare", "-b", "main", str(origin))
        run(self.root, "clone", "-q", str(origin), "r")
        self.path = self.root / "r"
        self.repo = RealRepo(self.path, observer=self.calls.append)
        self.wt: RealWorktree = self.repo.worktree(self.path)
        (self.path / "a.txt").write_text("one\n", encoding="utf-8")
        self.wt.record("first", paths="all")
        self.wt.push("main")
        self.calls.clear()

    def count(self, *words: str) -> int:
        return sum(all(w in call for w in words) for call in self.calls)

    def age(self, rel: str) -> None:
        """Make the file look old, as one a worker wrote minutes ago does."""
        target = self.path / rel
        then = time.time() - 600
        os.utime(target, (then, then))


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Rig:
    apply_hermetic_env(monkeypatch, identity=_ME, home=tmp_path / "home")
    return Rig(tmp_path)


def test_identity_is_asked_of_git_once(rig: Rig) -> None:
    for _ in range(3):
        rig.repo.identity()
    assert rig.count("--git-common-dir") == 1


def _remote_call(rig: Rig, operation: str, sha: Sha) -> object:
    operations: dict[str, Callable[[], object]] = {
        "push": lambda: rig.wt.push("main"),
        "push_known": lambda: rig.wt.push("main", head=sha),
        "push_refspecs": lambda: rig.wt.push_refspecs("origin", [f"{sha}:refs/heads/main"]),
        "push_request": lambda: rig.wt.push_request("origin", ["HEAD:refs/heads/main"]),
        "push_default": lambda: rig.wt.push_request(None, []),
        "push_lease": lambda: rig.wt.push_lease("origin", "HEAD:refs/heads/main"),
        "lfs_push": lambda: rig.wt.lfs_push("origin", ["HEAD"]),
        "fetch": rig.repo.fetch,
        "sync": rig.repo.sync,
        "delete_remote_at": lambda: rig.repo.delete_remote_at("origin", "refs/heads/main", sha, missing_ok=False),
        "ls_remote": lambda: rig.repo.ls_remote("origin"),
    }
    return operations[operation]()


@pytest.mark.parametrize("operation", _REMOTE_OPERATIONS)
def test_remote_operations_have_a_fixed_process_budget(rig: Rig, operation: str) -> None:
    sha = Sha(run(rig.path, "rev-parse", "HEAD").strip())
    run(rig.root / "o.git", "config", "receive.denyDeleteCurrent", "ignore")
    rig.calls.clear()
    _remote_call(rig, operation, sha)
    assert len(rig.calls) == (2 if operation == "push" else 1), rig.calls


@pytest.mark.parametrize("operation", _REMOTE_OPERATIONS)
@pytest.mark.parametrize("code", [0, 1])
def test_remote_results_preserve_complete_process_output(rig: Rig, monkeypatch: pytest.MonkeyPatch, operation: str, code: int) -> None:
    sha = Sha("a" * 40)
    stdout = f"{sha}\trefs/heads/main\n" if operation == "ls_remote" else "stdout-start\n" + "x\n" * 1000 + "stdout-end\n"
    if code and operation in {"push", "push_known", "push_refspecs", "delete_remote_at"}:
        stdout += "!\tHEAD:refs/heads/main\t[rejected] (stale info)\n"
    stderr = "stderr-start\n" + "detail\n" * 1000 + "stderr-end\n"

    def process(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if "rev-parse" in args:
            return subprocess.CompletedProcess(args, 0, (sha + "\n").encode(), b"")
        return subprocess.CompletedProcess(args, code, stdout.encode(), stderr.encode())

    monkeypatch.setattr(subprocess, "run", process)
    rig.calls.clear()
    try:
        result = _remote_call(rig, operation, sha)
    except GitUnavailable as exc:
        assert code and operation in {"fetch", "delete_remote_at", "ls_remote"}
        result = exc
    assert getattr(result, "output", None) == (stdout + stderr).strip()
    assert len(rig.calls) == (2 if operation == "push" else 1), rig.calls


@pytest.mark.parametrize("diagnostic", ["error: nope", ""])
def test_configured_pre_push_hook_is_observed_in_the_push_process(rig: Rig, monkeypatch: pytest.MonkeyPatch, diagnostic: str) -> None:
    hooks = rig.root / "custom-hooks"
    hooks.mkdir()
    hook = hooks / "pre-push"
    hook.write_text(f"#!/bin/sh\nprintf '%s' '{diagnostic}' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    apply_hermetic_env(monkeypatch, identity=_ME, home=rig.root / "home", config={"core.hooksPath": str(hooks)})
    sha = Sha(run(rig.path, "rev-parse", "HEAD").strip())
    rig.calls.clear()
    result = rig.wt.push_refspecs("origin", [f"{sha}:refs/heads/main"])
    assert type(result).__name__ == "HookRejected"
    assert diagnostic in result.output
    assert len(rig.calls) == 1


@pytest.mark.parametrize("hook_code", [0, 1, None])
def test_push_needs_a_failed_hook_exit_to_report_hook_rejection(rig: Rig, monkeypatch: pytest.MonkeyPatch, hook_code: int | None) -> None:
    output = "transport-start\n" + "detail\n" * 200 + "fatal: the remote end hung up unexpectedly\n"

    def process(args: list[str], *, env: dict[str, str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if hook_code is not None:
            events = [
                {"event": "child_start", "child_class": "hook", "hook_name": "pre-push", "child_id": 0},
                {"event": "child_exit", "child_id": 0, "code": hook_code},
            ]
            Path(env["GIT_TRACE2_EVENT"]).write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
        return subprocess.CompletedProcess(args, 128, b"", output.encode())

    monkeypatch.setattr(subprocess, "run", process)
    rig.calls.clear()
    result = rig.wt.push_refspecs("origin", [f"{'a' * 40}:refs/heads/main"])
    assert type(result).__name__ == ("HookRejected" if hook_code == 1 else "Transient")
    assert result.output == output.strip()
    assert len(rig.calls) == 1


@pytest.mark.parametrize("old_trace", [False, True])
def test_hook_failure_without_trace_evidence_is_unavailable(rig: Rig, monkeypatch: pytest.MonkeyPatch, *, old_trace: bool) -> None:
    output = "error: pre-push declined\n" + "detail\n" * 200

    def process(args: list[str], *, env: dict[str, str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if old_trace:
            events = [
                {"event": "child_start", "child_class": "hook", "child_id": 0},
                {"event": "child_exit", "child_id": 0, "code": 1},
            ]
            Path(env["GIT_TRACE2_EVENT"]).write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
        return subprocess.CompletedProcess(args, 1, b"", output.encode())

    monkeypatch.setattr(subprocess, "run", process)
    with pytest.raises(GitUnavailable) as caught:
        rig.wt.push_refspecs("origin", [f"{'a' * 40}:refs/heads/main"])
    assert caught.value.output == output.strip()


def test_push_hook_receives_the_pinned_object_as_its_local_ref(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    hook = rig.path / ".git" / "hooks" / "pre-push"
    hook.parent.mkdir(exist_ok=True)
    captured = rig.root / "push-stdin"
    hook.write_text(f"#!/bin/sh\ncat > '{captured}'\n", encoding="utf-8")
    hook.chmod(0o755)
    apply_hermetic_env(monkeypatch, identity=_ME, home=rig.root / "home", config={})
    sha = run(rig.path, "rev-parse", "HEAD").strip()
    result = rig.wt.push("new")
    assert type(result).__name__ == "Pushed"
    assert captured.read_text(encoding="utf-8").split() == [sha, sha, "refs/heads/new", "0" * 40]


@pytest.mark.parametrize(("source", "count"), [("HEAD:refs/heads/main", 2), ("HEAD", 3), ("main:refs/heads/main", 2)])
def test_symbolic_typed_pushes_document_the_resolution_budget(rig: Rig, source: str, count: int) -> None:
    rig.calls.clear()
    result = rig.wt.push_refspecs("origin", [source])
    assert type(result).__name__ == "Pushed"
    assert len(rig.calls) == count


def test_configured_remote_discovery_uses_one_config_query(rig: Rig) -> None:
    rig.calls.clear()
    result = rig.wt.push_request(None, ["HEAD:refs/heads/main"])
    assert result.ok
    assert len(rig.calls) == 3
    assert rig.count("config") == 1


@pytest.mark.parametrize("missing_ok", [False, True])
def test_absent_remote_deletion_only_probes_when_idempotency_is_requested(rig: Rig, *, missing_ok: bool) -> None:
    sha = Sha(run(rig.path, "rev-parse", "HEAD").strip())
    rig.calls.clear()
    if missing_ok:
        result = rig.repo.delete_remote_at("origin", "refs/heads/absent", sha)
        assert result.ok
        assert "stale info" in result.output
    else:
        with pytest.raises(GitUnavailable) as caught:
            rig.repo.delete_remote_at("origin", "refs/heads/absent", sha, missing_ok=False)
        assert "stale info" in caught.value.output
    assert len(rig.calls) == (2 if missing_ok else 1)


def test_deletion_verification_failure_retains_both_invocations(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    pushed = "push stdout\n" + "push detail\n" * 1000
    probed = "probe stdout\n" + "probe detail\n" * 1000

    def process(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        output = probed if "ls-remote" in args else pushed
        return subprocess.CompletedProcess(args, 1, output.encode(), b"error: refused\n")

    monkeypatch.setattr(subprocess, "run", process)
    rig.calls.clear()
    with pytest.raises(GitReadFailure) as caught:
        rig.repo.delete_remote_at("origin", "refs/heads/main", Sha("a" * 40))
    assert caught.value.output == (probed + "error: refused\n").strip()
    assert caught.value.push_output == (pushed + "error: refused\n").strip()
    assert len(rig.calls) == 2


def test_remote_hook_text_cannot_be_classified_as_a_ref_race(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    apply_hermetic_env(monkeypatch, identity=_ME, home=rig.root / "home", config={"maintenance.auto": "false"})
    hook = rig.root / "o.git" / "hooks" / "pre-receive"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\necho 'rejected by policy hook' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    sha = Sha(run(rig.path, "rev-parse", "HEAD").strip())
    rig.calls.clear()
    result = rig.wt.push_refspecs("origin", [f"{sha}:refs/heads/new"])
    assert type(result).__name__ == "RemoteRejected"
    assert "rejected by policy hook" in result.output
    assert len(rig.calls) == 1


@pytest.mark.parametrize("operation", ["push_lease", "lfs_push", "fetch", "sync", "ls_remote"])
def test_remote_timeouts_preserve_partial_output(rig: Rig, monkeypatch: pytest.MonkeyPatch, operation: str) -> None:
    output = b"stdout-start\n" + b"x\n" * 1000
    stderr = b"stderr-start\n" + b"detail\n" * 1000

    def process(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(args, 1, output=output, stderr=stderr)

    monkeypatch.setattr(subprocess, "run", process)
    rig.calls.clear()
    try:
        result = _remote_call(rig, operation, Sha("a" * 40))
    except GitUnavailable as exc:
        result = exc
    assert getattr(result, "output", None) == (output + stderr).decode().strip()
    assert len(rig.calls) == 1


@pytest.mark.parametrize("path_api", [False, True])
def test_malformed_advertisements_keep_complete_diagnostics(rig: Rig, monkeypatch: pytest.MonkeyPatch, *, path_api: bool) -> None:
    stdout = "not a ref row\n"
    stderr = "detail\n" * 1000

    def process(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
        if path_api:
            return subprocess.CompletedProcess(args, 0, stdout, stderr)
        return subprocess.CompletedProcess(args, 0, stdout.encode(), stderr.encode())

    monkeypatch.setattr(subprocess, "run", process)
    with pytest.raises(GitReadFailure) as caught:
        if path_api:
            porcelain.ls_remote(rig.path, "origin")
        else:
            rig.repo.ls_remote("origin")
    assert caught.value.output == (stdout + stderr).strip()


@pytest.mark.parametrize("operation", ["push", "fetch", "lfs_push", "lfs_fetch", "pull_rebase", "ls_remote", "readiness"])
@pytest.mark.parametrize("code", [0, 1])
def test_path_remote_operations_keep_complete_output_with_a_fixed_budget(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, operation: str, code: int
) -> None:
    stdout = "a" * 40 + "\trefs/heads/main\n"
    stderr = "detail\n" * 1000
    calls: list[list[str]] = []

    def process(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, code, stdout, stderr)

    monkeypatch.setattr(subprocess, "run", process)
    operations: dict[str, Callable[[], object]] = {
        "push": lambda: porcelain.push(rig.path, "origin"),
        "fetch": lambda: porcelain.fetch(rig.path, "origin"),
        "lfs_push": lambda: porcelain.lfs_push(rig.path, "origin", "HEAD"),
        "lfs_fetch": lambda: porcelain.lfs_fetch(rig.path, "origin", "HEAD"),
        "pull_rebase": lambda: porcelain.pull_rebase(rig.path, "origin", "main"),
        "ls_remote": lambda: porcelain.ls_remote(rig.path, "origin"),
        "readiness": lambda: porcelain.readiness(rig.path),
    }
    try:
        result = operations[operation]()
    except porcelain.GitError as exc:
        assert code
        result = exc
    output = result["output"] if isinstance(result, dict) else getattr(result, "output", None)
    assert output == (stdout + stderr).strip()
    assert len(calls) == (3 if operation == "readiness" else 1)


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [
        ("is_ancestor", "HEAD", "HEAD", True),
        ("is_ancestor", "HEAD~1", "HEAD", True),
        ("is_ancestor", "HEAD", "HEAD~1", False),
        ("merge_base", "HEAD~1", "HEAD", None),
    ],
)
def test_revision_reads_start_one_process_per_ask(rig: Rig, operation: str, a: str, b: str, expected: bool | None) -> None:
    root = run(rig.path, "rev-parse", "HEAD").strip()
    rig.wt.record("second", allow_empty=True)
    for _ in range(2):
        rig.calls.clear()
        if operation == "is_ancestor":
            assert rig.repo.is_ancestor(a, b) is expected
            assert rig.calls == [("merge-base", "--is-ancestor", "--end-of-options", a, b)]
        else:
            assert rig.repo.merge_base(a, b) == root
            assert rig.calls == [("merge-base", "--end-of-options", a, b)]


@pytest.mark.parametrize("detached", [False, True])
def test_branch_starts_one_process_per_ask(rig: Rig, *, detached: bool) -> None:
    if detached:
        run(rig.path, "checkout", "-q", "--detach")
    for _ in range(2):
        rig.calls.clear()
        assert rig.wt.branch() == (None if detached else "main")
        assert rig.calls == [("symbolic-ref", "--short", "-q", "HEAD")]


@pytest.mark.parametrize(("a", "b"), [("missing", "HEAD"), ("HEAD", "missing")])
def test_missing_ancestry_still_starts_only_one_process(rig: Rig, a: str, b: str) -> None:
    rig.calls.clear()
    with pytest.raises(MissingRevision):
        rig.repo.is_ancestor(a, b)
    assert rig.calls == [("merge-base", "--is-ancestor", "--end-of-options", a, b)]


def test_unrelated_revision_reads_each_start_one_process(rig: Rig) -> None:
    unrelated = run(rig.path, "commit-tree", "HEAD^{tree}", "-m", "another root").strip()
    rig.calls.clear()
    assert rig.repo.merge_base("HEAD", unrelated) is None
    assert rig.calls == [("merge-base", "--end-of-options", "HEAD", unrelated)]
    rig.calls.clear()
    assert rig.repo.is_ancestor("HEAD", unrelated) is False
    assert rig.calls == [("merge-base", "--is-ancestor", "--end-of-options", "HEAD", unrelated)]


@pytest.mark.parametrize("revision", ["--root", "--abort", "--all", "--independent", "-x"])
def test_option_like_revisions_start_no_process(rig: Rig, revision: str) -> None:
    rig.calls.clear()
    for operation in (rig.repo.is_ancestor, rig.repo.merge_base):
        for a, b in ((revision, "HEAD"), ("HEAD", revision)):
            with pytest.raises(ValueError, match="revision must not start"):
                operation(a, b)
    with pytest.raises(ValueError, match="revision must not start"):
        rig.wt.rebase(revision)
    assert rig.calls == []


def test_fast_forward_failure_is_typed_with_an_injected_non_english_locale(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    run(rig.path, "checkout", "-qb", "other")
    run(rig.path, "commit", "--allow-empty", "-qm", "other")
    run(rig.path, "checkout", "-q", "main")
    run(rig.path, "commit", "--allow-empty", "-qm", "local")
    repo = RealRepo(rig.path, env={"LC_ALL": "fr_FR.UTF-8", "LANG": "fr_FR.UTF-8"})
    wt = repo.worktree(rig.path)
    before = repo.history(["HEAD"])
    with pytest.raises(NotFastForward):
        wt.merge_ff("other")
    assert repo.history(["HEAD"]) == before


@pytest.mark.parametrize("operation", ["is_ancestor", "merge_base"])
@pytest.mark.parametrize("outcome", [Done(128, b"", "unknown read failure"), Done(0, b"malformed", "")])
def test_revision_read_failures_are_never_absence(rig: Rig, monkeypatch: pytest.MonkeyPatch, operation: str, outcome: Done) -> None:
    original = rig.repo.run

    def failed_read(
        cwd: Path,
        *args: str,
        check: bool = True,
        pin: bool = True,
        stdin: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> Done:
        if args[0] == "merge-base":
            return outcome
        return original(cwd, *args, check=check, pin=pin, stdin=stdin, env=env, timeout=timeout)

    monkeypatch.setattr(rig.repo, "run", failed_read)
    with pytest.raises(GitReadFailure):
        getattr(rig.repo, operation)("HEAD", "HEAD")


def test_memo_can_be_switched_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    apply_hermetic_env(monkeypatch, identity=_ME, home=tmp_path / "home")
    run(tmp_path, "init", "-q", "-b", "main", "x")
    calls: list[tuple[str, ...]] = []
    repo = RealRepo(tmp_path / "x", memoize=False, observer=calls.append)
    repo.identity()
    repo.identity()
    assert sum("--git-common-dir" in c for c in calls) == 2


def test_an_unchanged_tree_is_not_written_again(rig: Rig) -> None:
    (rig.path / "b.txt").write_text("b\n", encoding="utf-8")
    rig.age("b.txt")
    first = rig.wt.snapshot("origin/main")
    assert rig.count("write-tree") == 1
    again = rig.wt.snapshot("origin/main")
    assert again == first
    assert rig.count("write-tree") == 1
    assert rig.count("status") == 2  # the check that the work is the same is one status, never nothing


def test_an_edited_tree_is_written_again(rig: Rig) -> None:
    (rig.path / "b.txt").write_text("b\n", encoding="utf-8")
    rig.age("b.txt")
    first = rig.wt.snapshot("origin/main")
    (rig.path / "b.txt").write_text("c\n", encoding="utf-8")
    second = rig.wt.snapshot("origin/main")
    assert second.tree != first.tree
    assert rig.count("write-tree") == 2


def test_a_new_head_is_written_again_even_when_the_files_are_the_same(rig: Rig) -> None:
    first = rig.wt.snapshot("origin/main")
    assert rig.wt.record("empty", allow_empty=True).__class__.__name__ == "Recorded"
    second = rig.wt.snapshot("origin/main")
    assert second.head != first.head
    assert second.tree == first.tree
    assert rig.count("write-tree") == 2


def test_two_same_size_edits_in_one_tick_are_two_trees(rig: Rig) -> None:
    target = rig.path / "b.txt"
    target.write_text("aaaa\n", encoding="utf-8")
    first = rig.wt.snapshot("origin/main")
    before = target.stat()
    target.write_text("bbbb\n", encoding="utf-8")
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert target.stat().st_size == before.st_size
    assert target.stat().st_mtime_ns == before.st_mtime_ns
    assert rig.wt.snapshot("origin/main").tree != first.tree


def test_a_ref_name_answer_is_kept_until_the_ref_moves(rig: Rig) -> None:
    first = rig.repo.relate("HEAD", "origin/main")
    rig.repo.relate("HEAD", "origin/main")
    assert rig.count("merge-base") == 1
    assert rig.wt.record("ahead", allow_empty=True).__class__.__name__ == "Recorded"
    moved = rig.repo.relate("HEAD", "origin/main")
    assert (first.ahead, moved.ahead) == (0, 1)


def test_a_ref_moved_by_someone_else_is_seen(rig: Rig) -> None:
    rig.repo.relate("HEAD", "origin/main")
    run(rig.path, "-c", "user.name=o", "-c", "user.email=o@x.y", "commit", "-q", "--allow-empty", "-m", "outside")
    assert rig.repo.relate("HEAD", "origin/main").ahead == 1
    assert rig.count("merge-base") == 2


def test_an_answer_about_shas_is_kept_for_good(rig: Rig) -> None:
    head = rig.wt.snapshot("origin/main").head
    assert head is not None
    rig.calls.clear()
    for _ in range(2):
        rig.repo.relate(head, head)
        rig.wt.diff(head, head)
    assert rig.count("merge-base") == 1
    assert rig.count("--numstat") == 1


def test_branches_are_kept_until_a_branch_moves(rig: Rig) -> None:
    rig.repo.branches()
    rig.repo.branches("task/")
    assert rig.count("for-each-ref") == 1
    run(rig.path, "branch", "task/new")
    assert [name for name, _ in rig.repo.branches("task/")] == ["task/new"]
    assert rig.count("for-each-ref") == 2


def test_worktrees_are_kept_until_invalidated(rig: Rig) -> None:
    rig.repo.worktrees()
    rig.repo.worktrees()
    assert rig.count("worktree", "list") == 1
    run(rig.path, "worktree", "add", "-q", "--detach", str(rig.root / "w"), "HEAD")
    assert len(rig.repo.worktrees()) == 1
    rig.repo.invalidate()
    assert len(rig.repo.worktrees()) == 2


def test_an_own_write_clears_what_can_change(rig: Rig) -> None:
    rig.repo.worktrees()
    rig.repo.add_worktree(rig.root / "w", "HEAD")
    assert len(rig.repo.worktrees()) == 2


def test_health_is_two_processes_every_time(rig: Rig) -> None:
    rig.wt.health()
    rig.wt.health()
    assert rig.count("config") == 2
    assert rig.count("rev-parse", "--show-toplevel") == 2


def test_a_tree_lists_and_reads_once(rig: Rig) -> None:
    for _ in range(2):
        found = rig.repo.tree("HEAD")
        assert found is not None
        assert sorted(found.files) == ["a.txt"]
        assert found.read("a.txt") == b"one\n"
    assert rig.count("ls-tree") == 1
    assert rig.count("cat-file") == 1


def test_a_repository_on_the_reftable_backend_is_never_memoized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    apply_hermetic_env(monkeypatch, identity=_ME, home=tmp_path / "home")
    path = tmp_path / "t"
    run(tmp_path, "init", "-q", "-b", "main", "--ref-format=reftable", "t")
    calls: list[tuple[str, ...]] = []
    repo = RealRepo(path, observer=calls.append)
    wt = repo.worktree(path)
    (path / "a.txt").write_text("x\n", encoding="utf-8")
    wt.record("one", paths="all")
    calls.clear()
    repo.relate("HEAD", "main")
    repo.relate("HEAD", "main")
    assert sum("merge-base" in c for c in calls) == 2


def test_a_lost_ref_lock_is_retried_and_a_dead_origin_is_offline(rig: Rig) -> None:
    (rig.root / "o.git").rename(rig.root / "gone.git")
    assert rig.repo.sync().__class__.__name__ == "Offline"
    assert rig.count("fetch") == 1  # an unreachable origin is not a lock race: no retry
