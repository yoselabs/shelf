"""The task driver reads refs/config and updates a checkout through either implementation."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import pytest

import git_porcelain as porcelain
from git_porcelain import Identity, RealRepo, RefRace
from git_porcelain.testing import FakePlumbing, FakeRemote, FakeRepo, apply_hermetic_env
from git_porcelain.testing import git as run

if TYPE_CHECKING:
    from git_porcelain import Worktree
    from git_porcelain.plumbing import Plumbing


@pytest.fixture(params=["real", "fake"])
def plumbing(request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Plumbing, Path]:
    apply_hermetic_env(monkeypatch, identity=Identity("Author", "author@example.invalid"), home=tmp_path / "home")
    path = tmp_path / "repo"
    if request.param == "fake":
        remote = FakeRemote(str(tmp_path / "origin.git"))
        remote.advance("main", {"tracked": "base\n", ".gitignore": "*.input\n"})
        repo = FakeRepo.clone(remote, path)
        repo.set_config("task.value", "first\nsecond")
        wt = repo.worktree(path)
        wt.write_file("tracked", "changed\n")
        wt.write_file("new file", "new\n")
        wt.write_file("declared.input", "input\n")
        return repo.plumbing(), path
    run(tmp_path, "init", "--bare", "-q", "-b", "main", "origin.git")
    run(tmp_path, "clone", "-q", str(tmp_path / "origin.git"), str(path))
    (path / "tracked").write_text("base\n", encoding="utf-8")
    (path / ".gitignore").write_text("*.input\n", encoding="utf-8")
    run(path, "add", "-A")
    run(path, "commit", "-qm", "base")
    run(path, "push", "-q", "origin", "main")
    run(path, "config", "task.value", "first\nsecond")
    (path / "tracked").write_text("changed\n", encoding="utf-8")
    (path / "new file").write_text("new\n", encoding="utf-8")
    (path / "declared.input").write_text("input\n", encoding="utf-8")
    return porcelain, path


def test_refs_are_named_and_delete_is_compare_and_swap(plumbing: tuple[Plumbing, Path]) -> None:
    api, path = plumbing
    local = api.branches(path)
    assert [r.name for r in local] == ["main"]
    assert api.branches(path, "origin") == local
    assert api.ls_remote(path, "origin", "refs/heads/main") == [porcelain.Ref("refs/heads/main", local[0].oid)]
    assert api.ls_remote(path, "origin", "missing*") == []
    with pytest.raises(RefRace) as caught:
        api.delete_ref_at(path, "refs/remotes/origin/main", "1" * 40)
    assert caught.value.retryable is False
    assert api.branches(path, "origin") == local
    api.delete_ref_at(path, "refs/remotes/origin/main", local[0].oid)
    assert api.branches(path, "origin") == []


def test_config_and_symbolic_reads_preserve_absence_and_multiline_values(plumbing: tuple[Plumbing, Path]) -> None:
    api, path = plumbing
    assert api.config_get(path, "task.absent") is None
    assert api.config_get(path, "task.absent", "fallback") == "fallback"
    assert api.config_get(path, "task.value") == "first\nsecond"
    assert api.config_entries(path, r"^task\.") == [("task.value", "first\nsecond")]
    assert api.config_entries(path, "^absent\\.") == []
    assert api.symbolic_ref(path, "HEAD") == "refs/heads/main"
    assert api.symbolic_ref(path, "refs/heads/main") is None
    with pytest.raises(porcelain.GitUnavailable):
        api.config_entries(path, "[")


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        ("tracked", {".gitignore", "tracked"}),
        ("untracked", {"new file"}),
        ("ignored", {"declared.input"}),
        ("all", {".gitignore", "tracked", "new file", "declared.input"}),
    ],
)
def test_file_scopes(plumbing: tuple[Plumbing, Path], scope: str, expected: set[str]) -> None:
    api, path = plumbing
    assert set(api.ls_files(path, scope=scope)) == expected
    assert api.check_ignore(path, ["tracked", "new file", "declared.input"]) == {"declared.input"}
    assert api.check_ignore(path, []) == set()


def test_fast_forward_preserves_edits_and_pull_rebase_refuses_a_dirty_tree(plumbing: tuple[Plumbing, Path]) -> None:
    api, path = plumbing
    api.merge_ff(path, "origin/main")
    # Pull's rebase requires a clean tree, even if the remote has not moved.
    with pytest.raises(porcelain.GitError):
        api.pull_rebase(path, "origin", "main")
    with pytest.raises(porcelain.MissingRevision):
        api.merge_ff(path, "does-not-exist")


@pytest.mark.parametrize("revision", ["--root", "--abort", "--all", "--independent", "-x"])
def test_fast_forward_rejects_option_like_revisions(plumbing: tuple[Plumbing, Path], revision: str) -> None:
    api, path = plumbing
    before = api.branches(path)
    with pytest.raises(ValueError, match="revision must not start"):
        api.merge_ff(path, revision)
    assert api.branches(path) == before


def _worktree(api: Plumbing, path: Path) -> Worktree:
    return FakeRepo(api.state, path).worktree(path) if isinstance(api, FakePlumbing) else RealRepo(path).worktree(path)


def test_snapshot_includes_declared_ignored_inputs_on_both_implementations(plumbing: tuple[Plumbing, Path]) -> None:
    api, path = plumbing
    wt = _worktree(api, path)
    ordinary = wt.snapshot("HEAD")
    declared = wt.snapshot("HEAD", inputs=["declared.input"])
    assert ordinary.tree != declared.tree
    tree = wt.repo.tree(str(declared.tree))
    assert tree is not None
    assert set(tree.files) == {".gitignore", "tracked", "new file", "declared.input"}
    assert tree.read("tracked") == b"changed\n"
    assert tree.read("new file") == b"new\n"
    assert tree.read("declared.input") == b"input\n"
    assert wt.snapshot("HEAD").tree == ordinary.tree


def test_read_failures_are_typed_and_invalid_scopes_are_refused(plumbing: tuple[Plumbing, Path]) -> None:
    api, path = plumbing
    with pytest.raises(porcelain.NotARepo):
        api.branches(path.parent / "missing")
    with pytest.raises(ValueError, match="scope"):
        api.ls_files(path, scope="bogus")


def _advance_remote(api: Plumbing, path: Path) -> None:
    if isinstance(api, FakePlumbing):
        remote = FakeRemote(str(path.parent / "origin.git"))
        remote.state = api.state.remote_repos["origin"]
        remote.advance("main", {"remote": "remote\n"})
    else:
        other = path.parent / "other"
        run(path.parent, "clone", "-q", str(path.parent / "origin.git"), str(other))
        (other / "remote").write_text("remote\n", encoding="utf-8")
        run(other, "add", "-A")
        run(other, "commit", "-qm", "remote")
        run(other, "push", "-q", "origin", "main")


def test_pull_fetches_and_rebases_local_commits(plumbing: tuple[Plumbing, Path]) -> None:
    api, path = plumbing
    wt = _worktree(api, path)
    wt.record("local", paths="all")
    _advance_remote(api, path)
    api.pull_rebase(path, "origin", "main")
    assert wt.repo.relate("origin/main", "HEAD").ahead == 0
    assert wt.repo.relate("origin/main", "HEAD").behind == 1
    tree = wt.repo.tree("HEAD")
    assert tree is not None
    assert tree.read("remote") == b"remote\n"
    assert tree.read("tracked") == b"changed\n"


@pytest.mark.parametrize("diverged", [False, True])
def test_merge_fast_forwards_and_refuses_divergence(
    plumbing: tuple[Plumbing, Path], monkeypatch: pytest.MonkeyPatch, *, diverged: bool
) -> None:
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    monkeypatch.setenv("LC_ALL", "fr_FR.UTF-8")
    api, path = plumbing
    wt = _worktree(api, path)
    if diverged:
        wt.record("local", paths="all")
    _advance_remote(api, path)
    wt.repo.sync()
    if diverged:
        before = api.branches(path)
        with pytest.raises(porcelain.GitError):
            api.merge_ff(path, "origin/main")
        assert api.branches(path) == before
    else:
        # The upstream only adds "remote", so local tracked edits survive.
        api.merge_ff(path, "origin/main")
        assert api.branches(path) == api.branches(path, "origin")
        assert wt.snapshot("HEAD").tree != wt.snapshot("HEAD").head_tree


def test_branch_pinned_reports_the_holder_from_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    apply_hermetic_env(monkeypatch, identity=Identity("Author", "author@example.invalid"), home=tmp_path / "home")
    run(tmp_path, "init", "-q", "-b", "main")
    run(tmp_path, "commit", "--allow-empty", "-qm", "base")
    linked = tmp_path / "linked"
    run(tmp_path, "worktree", "add", "--detach", str(linked), "HEAD")
    with pytest.raises(porcelain.BranchPinned) as caught:
        porcelain.run_git(linked, "checkout", "main")
    assert caught.value.holder == str(tmp_path)


def test_snapshot_matches_taskloop_throwaway_index_with_declared_ignored_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    apply_hermetic_env(monkeypatch, identity=Identity("Author", "author@example.invalid"), home=tmp_path / "home")
    run(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / ".gitignore").write_text("*.input\n", encoding="utf-8")
    (tmp_path / "tracked").write_text("base", encoding="utf-8")
    run(tmp_path, "add", "-A")
    run(tmp_path, "commit", "-qm", "base")
    (tmp_path / "tracked").write_text("changed", encoding="utf-8")
    (tmp_path / "new").write_text("new", encoding="utf-8")
    (tmp_path / "declared.input").write_text("input", encoding="utf-8")
    wt = RealRepo(tmp_path).worktree(tmp_path)
    before = run(tmp_path, "ls-files", "--stage", "-z")
    state_before = run(tmp_path, "--no-optional-locks", "status", "--porcelain=v2", "--branch", "-z", "--untracked-files=all")
    default = wt.snapshot("HEAD")
    first = wt.snapshot("HEAD", inputs=["declared.input"])
    (tmp_path / "declared.input").write_text("other", encoding="utf-8")
    second = wt.snapshot("HEAD", inputs=["declared.input"])
    assert first.tree != second.tree
    assert wt.snapshot("HEAD") == default
    assert state_before == run(tmp_path, "--no-optional-locks", "status", "--porcelain=v2", "--branch", "-z", "--untracked-files=all")
    assert before == run(tmp_path, "ls-files", "--stage", "-z")
    # treehash.state_of is a status/stat signature, not a tree id. tree_of's
    # independent throwaway-index algorithm is the reference for Snapshot.tree.
    with TemporaryDirectory() as folder:
        env = {"GIT_INDEX_FILE": str(Path(folder) / "index")}
        porcelain.run_git(tmp_path, "read-tree", "HEAD", env=env)
        porcelain.run_git(tmp_path, "add", "-A", env=env)
        expected = porcelain.run_git(tmp_path, "write-tree", env=env).strip()
        assert wt.snapshot("HEAD").tree == expected
        porcelain.run_git(tmp_path, "add", "-f", "declared.input", env=env)
        expected_input = porcelain.run_git(tmp_path, "write-tree", env=env).strip()
        assert second.tree == expected_input
    assert before == run(tmp_path, "ls-files", "--stage", "-z")
