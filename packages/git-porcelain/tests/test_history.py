"""git_porcelain — the history surface: exact-path commits, log search, reads at a revision,
status entries, and push/fetch with classified failures.

Real temp repos and a real bare remote; no subprocess mocking.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import git_porcelain as git
import pytest
from git_porcelain import GitError, Identity, RemoteError

if TYPE_CHECKING:
    from pathlib import Path


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


def _init(path: Path, *, identity: bool = True) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    if identity:
        _git(path, "config", "user.email", "t@example.com")
        _git(path, "config", "user.name", "Tester")
    return path


def _seed(repo: Path) -> None:
    (repo / "seed.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=S", "-c", "user.email=s@example.com", "commit", "-qm", "seed")


ROBIN = Identity("Robin Vale", "robin@example.com")
BOT = Identity("a2kay", "a2kay@example.invalid")


# --- commit_paths ------------------------------------------------------------------


def test_commit_paths_commits_only_the_named_paths(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    (repo / "a.md").write_text("a\n", encoding="utf-8")
    (repo / "b.md").write_text("b\n", encoding="utf-8")

    sha = git.commit_paths(repo, ["a.md"], "write a", author=ROBIN, committer=BOT)

    assert sha is not None
    assert _git(repo, "show", "--name-only", "--format=", sha).split() == ["a.md"]
    assert "b.md" in git.dirty_rels(repo)


def test_commit_paths_ignores_what_was_already_staged_elsewhere(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    (repo / "hand.md").write_text("staged by hand\n", encoding="utf-8")
    _git(repo, "add", "hand.md")
    (repo / "a.md").write_text("a\n", encoding="utf-8")

    sha = git.commit_paths(repo, ["a.md"], "write a", author=ROBIN, committer=BOT)

    assert sha is not None
    assert _git(repo, "show", "--name-only", "--format=", sha).split() == ["a.md"]
    assert "hand.md" in _git(repo, "diff", "--cached", "--name-only")


def test_commit_paths_records_a_deletion_and_a_rename(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    (repo / "old.md").write_text("body\n" * 20, encoding="utf-8")
    git.commit_paths(repo, ["old.md"], "add", author=ROBIN, committer=BOT)
    (repo / "old.md").rename(repo / "new.md")
    (repo / "seed.md").unlink()

    sha = git.commit_paths(repo, ["old.md", "new.md", "seed.md"], "move and delete", author=ROBIN, committer=BOT)

    assert sha is not None
    status = _git(repo, "show", "-M", "--name-status", "--format=", sha).split("\n")
    assert any(line.startswith("R") and "old.md" in line and "new.md" in line for line in status)
    assert any(line.startswith("D") and "seed.md" in line for line in status)
    assert git.dirty_rels(repo) == []


def test_commit_paths_returns_none_when_nothing_changed(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    assert git.commit_paths(repo, ["seed.md", "missing.md"], "noop", author=ROBIN, committer=BOT) is None
    assert git.commit_paths(repo, [], "noop", author=ROBIN, committer=BOT) is None


def test_commit_paths_writes_trailers_author_and_committer(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    (repo / "a.md").write_text("a\n", encoding="utf-8")

    sha = git.commit_paths(
        repo,
        ["a.md"],
        "create note/a",
        trailers=[("A2kay-Entity", "kay://entity/note/a"), ("A2kay-Trace", "t1")],
        author=ROBIN,
        committer=BOT,
    )

    assert sha is not None
    fmt = _git(repo, "show", "-s", "--format=%an|%ae|%cn|%ce|%s", sha).strip()
    assert fmt == "Robin Vale|robin@example.com|a2kay|a2kay@example.invalid|create note/a"
    trailers = _git(repo, "show", "-s", "--format=%(trailers:only,unfold)", sha)
    assert "A2kay-Entity: kay://entity/note/a" in trailers
    assert "A2kay-Trace: t1" in trailers


def test_commit_paths_commits_without_any_configured_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = _init(tmp_path / "repo", identity=False)
    (repo / "a.md").write_text("a\n", encoding="utf-8")

    assert git.commit_paths(repo, ["a.md"], "first", author=ROBIN, committer=BOT) is not None


def test_commit_paths_skips_a_failing_pre_commit_hook(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    (repo / "a.md").write_text("a\n", encoding="utf-8")

    assert git.commit_paths(repo, ["a.md"], "write", author=ROBIN, committer=BOT) is not None


def test_commit_paths_handles_non_ascii_paths(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    rel = "Люди/робин.md"
    (repo / "Люди").mkdir()
    (repo / rel).write_text("x\n", encoding="utf-8")

    assert git.dirty_rels(repo) == [rel]
    assert git.commit_paths(repo, [rel], "write", author=ROBIN, committer=BOT) is not None
    assert git.dirty_rels(repo) == []


def test_commit_paths_raises_when_the_index_is_locked(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    (repo / ".git" / "index.lock").write_text("", encoding="utf-8")
    (repo / "a.md").write_text("a\n", encoding="utf-8")

    with pytest.raises(GitError):
        git.commit_paths(repo, ["a.md"], "write", author=ROBIN, committer=BOT)
    assert (repo / ".git" / "index.lock").exists()


# --- status ------------------------------------------------------------------------


def test_status_tells_tracked_from_untracked(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    (repo / "seed.md").write_text("changed\n", encoding="utf-8")
    (repo / "new.md").write_text("new\n", encoding="utf-8")

    by_path = {e.path: e for e in git.status(repo)}

    assert by_path["seed.md"].tracked is True
    assert by_path["new.md"].tracked is False


def test_status_reports_a_staged_rename_with_its_origin(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    _git(repo, "mv", "seed.md", "moved.md")

    entries = git.status(repo)

    assert [(e.path, e.orig_path) for e in entries] == [("moved.md", "seed.md")]


# --- log_grep / show_at ------------------------------------------------------------


def test_log_grep_finds_commits_by_trailer_across_a_move(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    uri = "kay://entity/note/robin"
    (repo / "robin.md").write_text("v1\n", encoding="utf-8")
    first = git.commit_paths(repo, ["robin.md"], "create", trailers=[("A2kay-Entity", uri)], author=ROBIN, committer=BOT)
    (repo / "robin.md").rename(repo / "robin-vale.md")
    second = git.commit_paths(repo, ["robin.md", "robin-vale.md"], "move", trailers=[("A2kay-Entity", uri)], author=ROBIN, committer=BOT)
    (repo / "other.md").write_text("x\n", encoding="utf-8")
    git.commit_paths(repo, ["other.md"], "other", trailers=[("A2kay-Entity", "kay://entity/note/other")], author=ROBIN, committer=BOT)

    found = git.log_grep(repo, f"^A2kay-Entity: {uri}$", limit=10)

    assert [c.sha for c in found] == [second, first]
    assert found[0].subject == "move"
    assert found[0].author == ROBIN
    assert ("A2kay-Entity", uri) in found[0].trailers
    assert set(found[0].paths) == {"robin.md", "robin-vale.md"}
    assert found[1].at.tzinfo is not None


def test_log_grep_on_an_empty_repo_is_empty(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    assert git.log_grep(repo, "anything", limit=5) == []


def test_show_at_reads_a_past_version_or_none(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    first = git.head(repo)
    (repo / "seed.md").write_text("second\n", encoding="utf-8")
    git.commit_paths(repo, ["seed.md"], "edit", author=ROBIN, committer=BOT)

    assert git.show_at(repo, "seed.md", first) == "seed\n"
    assert git.show_at(repo, "never.md", first) is None


# --- remote: push / fetch / is_ancestor --------------------------------------------


def _with_remote(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    repo = _init(tmp_path / "repo")
    _seed(repo)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "main")
    return repo, remote


def test_push_sends_new_commits_and_upstream_names_the_branch(tmp_path: Path) -> None:
    repo, remote = _with_remote(tmp_path)
    (repo / "a.md").write_text("a\n", encoding="utf-8")
    sha = git.commit_paths(repo, ["a.md"], "a", author=ROBIN, committer=BOT)

    assert git.upstream(repo) == "origin/main"
    git.push(repo)

    assert _git(remote, "rev-parse", "main").strip() == sha


def test_push_to_an_explicit_refspec(tmp_path: Path) -> None:
    repo, remote = _with_remote(tmp_path)
    git.push(repo, "origin", "HEAD:refs/heads/a2kay/diverged/box/20260929-1200")
    assert _git(remote, "rev-parse", "a2kay/diverged/box/20260929-1200").strip() == git.head(repo)


def test_fetch_then_is_ancestor_detects_divergence(tmp_path: Path) -> None:
    repo, remote = _with_remote(tmp_path)
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(remote), str(other))
    (other / "b.md").write_text("b\n", encoding="utf-8")
    _git(other, "add", "b.md")
    _git(other, "-c", "user.name=O", "-c", "user.email=o@example.com", "commit", "-qm", "elsewhere")
    _git(other, "push", "-q")
    (repo / "a.md").write_text("a\n", encoding="utf-8")
    git.commit_paths(repo, ["a.md"], "here", author=ROBIN, committer=BOT)

    git.fetch(repo)

    assert git.is_ancestor(repo, "origin/main", "HEAD") is False
    with pytest.raises(RemoteError) as info:
        git.push(repo)
    assert info.value.reason == "rejected"


def test_is_ancestor_true_for_a_fast_forward(tmp_path: Path) -> None:
    repo, _ = _with_remote(tmp_path)
    (repo / "a.md").write_text("a\n", encoding="utf-8")
    git.commit_paths(repo, ["a.md"], "a", author=ROBIN, committer=BOT)
    assert git.is_ancestor(repo, "origin/main", "HEAD") is True


def test_push_to_a_missing_remote_is_offline(tmp_path: Path) -> None:
    repo, remote = _with_remote(tmp_path)
    remote.rename(tmp_path / "gone.git")
    with pytest.raises(RemoteError) as info:
        git.push(repo)
    assert info.value.reason in {"offline", "auth"}
    assert info.value.retryable is (info.value.reason == "offline")


def test_classify_remote_failure_reads_git_stderr() -> None:
    assert git.classify_remote_failure("fatal: Authentication failed for 'https://x'") == "auth"
    assert git.classify_remote_failure("git@github.com: Permission denied (publickey).") == "auth"
    assert git.classify_remote_failure("fatal: could not read Username for 'https://github.com'") == "auth"
    assert git.classify_remote_failure("! [rejected]        main -> main (fetch first)") == "rejected"
    assert git.classify_remote_failure("! [rejected] main -> main (non-fast-forward)") == "rejected"
    assert git.classify_remote_failure("fatal: unable to access 'https://x/': Could not resolve host: x") == "offline"
    assert git.classify_remote_failure("ssh: connect to host x port 22: Network is unreachable") == "offline"
    assert git.classify_remote_failure("something else entirely") == "other"


def test_upstream_is_none_without_tracking(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    assert git.upstream(repo) is None


def test_commit_paths_stages_a_moved_directory_by_its_old_and_new_path(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    (repo / "Projects" / "p1" / "attachments").mkdir(parents=True)
    (repo / "Projects" / "p1" / "README.md").write_text("p1\n" * 10, encoding="utf-8")
    (repo / "Projects" / "p1" / "attachments" / "a.txt").write_text("att\n" * 10, encoding="utf-8")
    git.commit_paths(repo, ["Projects/p1"], "add", author=ROBIN, committer=BOT)
    (repo / "Archive").mkdir()
    (repo / "Projects" / "p1").rename(repo / "Archive" / "p1")

    sha = git.commit_paths(repo, ["Projects/p1", "Archive/p1"], "move", author=ROBIN, committer=BOT)

    assert sha is not None
    assert git.dirty_rels(repo) == []
    assert sorted(_git(repo, "ls-files").split()) == ["Archive/p1/README.md", "Archive/p1/attachments/a.txt", "seed.md"]


def test_commit_paths_skips_an_ignored_path_it_was_handed(tmp_path: Path) -> None:
    repo = _init(tmp_path / "repo")
    _seed(repo)
    (repo / ".gitignore").write_text("*.distilled.md\n", encoding="utf-8")
    (repo / "a.md").write_text("a\n", encoding="utf-8")
    (repo / "a.distilled.md").write_text("derived\n", encoding="utf-8")

    sha = git.commit_paths(repo, ["a.md", "a.distilled.md"], "write", author=ROBIN, committer=BOT)

    assert sha is not None
    assert _git(repo, "show", "--name-only", "--format=", sha).split() == ["a.md"]
    assert git.commit_paths(repo, ["a.distilled.md"], "write", author=ROBIN, committer=BOT) is None


# --- merge / finish_merge ----------------------------------------------------------


def _pair(tmp_path: Path) -> tuple[Path, Path]:
    """A repo with an upstream, and a second clone of that upstream that can push to it."""
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    repo = _init(tmp_path / "repo")
    _seed(repo)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "main")
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(remote), str(other))
    return repo, other


def _write_commit(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "-c", "user.name=S", "-c", "user.email=s@example.com", "commit", "-qm", f"write {name}")


def _publish(other: Path, name: str, text: str) -> None:
    _write_commit(other, name, text)
    _git(other, "push", "-q")


def _parents(repo: Path) -> list[str]:
    return _git(repo, "show", "-s", "--format=%P", "HEAD").split()


def test_merge_of_an_ancestor_is_up_to_date(tmp_path: Path) -> None:
    repo, _ = _pair(tmp_path)
    _write_commit(repo, "a.md", "a\n")
    git.fetch(repo)
    result = git.merge(repo, "origin/main", author=ROBIN, committer=BOT)
    assert result.state == "up_to_date"
    assert result.changed == ()


def test_merge_fast_forwards_when_only_the_remote_moved(tmp_path: Path) -> None:
    repo, other = _pair(tmp_path)
    _publish(other, "b.md", "b\n")
    git.fetch(repo)

    result = git.merge(repo, "origin/main", author=ROBIN, committer=BOT)

    assert result.state == "fast_forward"
    assert result.changed == ("b.md",)
    assert (repo / "b.md").read_text(encoding="utf-8") == "b\n"
    assert len(_parents(repo)) == 1


def test_merge_of_disjoint_work_makes_a_merge_commit_with_identity_and_trailers(tmp_path: Path) -> None:
    repo, other = _pair(tmp_path)
    _publish(other, "b.md", "b\n")
    _write_commit(repo, "a.md", "a\n")
    git.fetch(repo)

    result = git.merge(repo, "origin/main", author=ROBIN, committer=BOT, message="sync", trailers=[("X-Why", "test")])

    assert result.state == "merged"
    assert result.changed == ("b.md",)
    assert len(_parents(repo)) == 2
    assert _git(repo, "show", "-s", "--format=%an|%cn|%s", "HEAD").strip() == "Robin Vale|a2kay|sync"
    assert "X-Why: test" in _git(repo, "show", "-s", "--format=%B", "HEAD")
    assert _git(repo, "status", "--porcelain") == ""


def test_merge_that_conflicts_leaves_markers_with_the_base_and_names_the_paths(tmp_path: Path) -> None:
    repo, other = _pair(tmp_path)
    _publish(other, "seed.md", "theirs\n")
    _write_commit(repo, "seed.md", "ours\n")
    git.fetch(repo)

    result = git.merge(repo, "origin/main", author=ROBIN, committer=BOT)

    assert result.state == "conflict"
    assert result.conflicted == ("seed.md",)
    assert git.merge_in_progress(repo)
    text = (repo / "seed.md").read_text(encoding="utf-8")
    assert "<<<<<<<" in text
    assert "|||||||" in text  # the common base is shown, so a resolver sees what each side changed
    assert git.has_conflict_markers(repo / "seed.md")


def test_merge_blocked_by_a_local_edit_changes_nothing(tmp_path: Path) -> None:
    repo, other = _pair(tmp_path)
    _publish(other, "seed.md", "theirs\n")
    (repo / "seed.md").write_text("uncommitted\n", encoding="utf-8")
    git.fetch(repo)

    result = git.merge(repo, "origin/main", author=ROBIN, committer=BOT)

    assert result.state == "blocked"
    assert result.error
    assert not git.merge_in_progress(repo)
    assert (repo / "seed.md").read_text(encoding="utf-8") == "uncommitted\n"


def test_merge_skips_hooks(tmp_path: Path) -> None:
    repo, other = _pair(tmp_path)
    _publish(other, "b.md", "b\n")
    _write_commit(repo, "a.md", "a\n")
    for hook in ("pre-merge-commit", "commit-msg"):
        path = repo / ".git" / "hooks" / hook
        path.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        path.chmod(0o755)
    git.fetch(repo)

    assert git.merge(repo, "origin/main", author=ROBIN, committer=BOT).state == "merged"


def test_finish_merge_waits_until_the_markers_are_gone_then_commits(tmp_path: Path) -> None:
    repo, other = _pair(tmp_path)
    _publish(other, "seed.md", "theirs\n")
    _publish(other, "b.md", "b\n")
    _write_commit(repo, "seed.md", "ours\n")
    git.fetch(repo)
    git.merge(repo, "origin/main", author=ROBIN, committer=BOT)

    early = git.finish_merge(repo, ["seed.md"], author=ROBIN, committer=BOT, message="sync")
    assert early.state == "conflict"
    assert early.conflicted == ("seed.md",)

    (repo / "seed.md").write_text("ours and theirs\n", encoding="utf-8")  # fixed by hand, never `git add`-ed
    done = git.finish_merge(repo, ["seed.md"], author=ROBIN, committer=BOT, message="sync")

    assert done.state == "merged"
    assert sorted(done.changed) == ["b.md", "seed.md"]
    assert not git.merge_in_progress(repo)
    assert len(_parents(repo)) == 2
    assert _git(repo, "status", "--porcelain") == ""


def test_finish_merge_accepts_a_file_deleted_to_resolve_it(tmp_path: Path) -> None:
    repo, other = _pair(tmp_path)
    _publish(other, "seed.md", "theirs\n")
    _write_commit(repo, "seed.md", "ours\n")
    git.fetch(repo)
    git.merge(repo, "origin/main", author=ROBIN, committer=BOT)
    (repo / "seed.md").unlink()

    assert git.finish_merge(repo, ["seed.md"], author=ROBIN, committer=BOT).state == "merged"
    assert "seed.md" not in _git(repo, "ls-files")


def test_finish_merge_without_a_merge_in_progress_is_up_to_date(tmp_path: Path) -> None:
    repo, _ = _pair(tmp_path)
    assert git.finish_merge(repo, [], author=ROBIN, committer=BOT).state == "up_to_date"
