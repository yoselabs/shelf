"""git_porcelain — commits a server makes many times a second: caller config reaches the
commit, so hooks and auto-maintenance stay off, and one commit costs few git processes.

Real temp repos; the host's global and system git config is shut out so a hooksPath or
maintenance setting on the machine cannot decide the outcome.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import git_porcelain as git
import pytest
from git_porcelain import Identity, porcelain

if TYPE_CHECKING:
    from pathlib import Path

ROBIN = Identity("Robin Vale", "robin@example.com")
BOT = Identity("a2kay", "a2kay@example.invalid")
QUIET = {"core.hooksPath": "/dev/null", "maintenance.auto": "false"}


@pytest.fixture(autouse=True)
def _no_host_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "seed.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=S", "-c", "user.email=s@example.com", "commit", "-qm", "seed")
    return repo


def _post_commit_hook(repo: Path, tmp_path: Path) -> Path:
    """A post-commit hook that leaves a marker; ``--no-verify`` does not stop this one."""
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    marker = tmp_path / "ran"
    hook = hooks / "post-commit"
    hook.write_text(f"#!/bin/sh\necho ran >> '{marker}'\n", encoding="utf-8")
    hook.chmod(0o755)
    _git(repo, "config", "core.hooksPath", str(hooks))
    return marker


# --- config= reaches the commit ----------------------------------------------------


def test_commit_paths_runs_the_post_commit_hook_by_default(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    marker = _post_commit_hook(repo, tmp_path)
    (repo / "a.md").write_text("a\n", encoding="utf-8")

    git.commit_paths(repo, ["a.md"], "write", author=ROBIN, committer=BOT)

    assert marker.exists()


def test_commit_paths_with_hooks_path_dev_null_runs_no_hook(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    marker = _post_commit_hook(repo, tmp_path)
    (repo / "a.md").write_text("a\n", encoding="utf-8")

    assert git.commit_paths(repo, ["a.md"], "write", author=ROBIN, committer=BOT, config=QUIET) is not None

    assert not marker.exists()


def _traced_commit(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: dict[str, str] | None) -> str:
    trace = tmp_path / "trace"
    monkeypatch.setenv("GIT_TRACE", str(trace))
    (repo / "a.md").write_text("a\n", encoding="utf-8")
    git.commit_paths(repo, ["a.md"], "write", author=ROBIN, committer=BOT, config=config)
    return trace.read_text(encoding="utf-8")


def test_commit_paths_starts_auto_maintenance_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trace = _traced_commit(_repo(tmp_path), tmp_path, monkeypatch, {"core.hooksPath": "/dev/null"})
    assert "built-in: git" in trace
    assert "maintenance run --auto" in trace


def test_commit_paths_with_maintenance_auto_false_starts_no_maintenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trace = _traced_commit(_repo(tmp_path), tmp_path, monkeypatch, QUIET)
    assert "built-in: git" in trace  # tracing was live
    assert "maintenance" not in trace


def test_merge_and_finish_merge_take_config(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    repo = _repo(tmp_path)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "main")
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(remote), str(other))
    for clone, name, text in ((other, "seed.md", "theirs\n"), (repo, "seed.md", "ours\n")):
        (clone / name).write_text(text, encoding="utf-8")
        _git(clone, "-c", "user.name=S", "-c", "user.email=s@example.com", "commit", "-qam", "edit")
    _git(other, "push", "-q")
    marker = _post_commit_hook(repo, tmp_path)
    git.fetch(repo)

    assert git.merge(repo, "origin/main", author=ROBIN, committer=BOT, config=QUIET).state == "conflict"
    (repo / "seed.md").write_text("resolved\n", encoding="utf-8")
    assert git.finish_merge(repo, ["seed.md"], author=ROBIN, committer=BOT, config=QUIET).state == "merged"

    assert not marker.exists()


def test_config_cannot_override_the_merge_conflict_style(tmp_path: Path) -> None:
    """The base section (diff3) is part of merge's contract; a caller's config comes first."""
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    repo = _repo(tmp_path)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "main")
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(remote), str(other))
    for clone, text in ((other, "theirs\n"), (repo, "ours\n")):
        (clone / "seed.md").write_text(text, encoding="utf-8")
        _git(clone, "-c", "user.name=S", "-c", "user.email=s@example.com", "commit", "-qam", "edit")
    _git(other, "push", "-q")
    git.fetch(repo)

    git.merge(repo, "origin/main", author=ROBIN, committer=BOT, config={"merge.conflictStyle": "merge"})

    assert "|||||||" in (repo / "seed.md").read_text(encoding="utf-8")


# --- few processes per commit ------------------------------------------------------


def _count_forks(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []
    real = subprocess.run

    def counting(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return real(cmd, **kwargs)  # type: ignore[call-overload]  # pyright: ignore[reportCallIssue, reportArgumentType]

    monkeypatch.setattr(porcelain.subprocess, "run", counting)
    return calls


@pytest.mark.parametrize(("name", "text"), [("new.md", "new\n"), ("seed.md", "edited\n")])
def test_a_commit_of_one_file_costs_three_git_processes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, text: str) -> None:
    repo = _repo(tmp_path)
    (repo / name).write_text(text, encoding="utf-8")
    calls = _count_forks(monkeypatch)

    sha = git.commit_paths(repo, [name], "write", author=ROBIN, committer=BOT, config=QUIET)

    assert len(calls) == 3, [c[3:5] for c in calls]
    monkeypatch.undo()
    assert sha == _git(repo, "rev-parse", "HEAD").strip()


def test_nothing_to_commit_costs_two_git_processes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    calls = _count_forks(monkeypatch)

    assert git.commit_paths(repo, ["seed.md"], "noop", author=ROBIN, committer=BOT) is None

    assert len(calls) == 2


# --- the returned sha, wherever HEAD keeps it --------------------------------------


def test_commit_paths_returns_the_sha_on_a_detached_head(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "--detach")
    (repo / "a.md").write_text("a\n", encoding="utf-8")

    sha = git.commit_paths(repo, ["a.md"], "write", author=ROBIN, committer=BOT)

    assert sha == _git(repo, "rev-parse", "HEAD").strip()


def test_commit_paths_returns_the_sha_in_a_linked_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    tree = tmp_path / "tree"
    _git(repo, "worktree", "add", "-q", "-b", "side", str(tree))
    _git(repo, "pack-refs", "--all")  # the main branch now lives only in packed-refs
    (tree / "a.md").write_text("a\n", encoding="utf-8")

    sha = git.commit_paths(tree, ["a.md"], "write", author=ROBIN, committer=BOT)

    assert sha == _git(tree, "rev-parse", "HEAD").strip()
    assert sha != _git(repo, "rev-parse", "HEAD").strip()


def test_commit_paths_returns_the_sha_when_refs_are_not_loose_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main", "--ref-format=reftable")
    (repo / "a.md").write_text("a\n", encoding="utf-8")

    sha = git.commit_paths(repo, ["a.md"], "first", author=ROBIN, committer=BOT)

    assert sha == _git(repo, "rev-parse", "HEAD").strip()


def test_commit_paths_first_commit_on_an_unborn_branch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "a.md").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "a.md")  # tracked but never committed: the change check has no HEAD

    sha = git.commit_paths(repo, ["a.md"], "first", author=ROBIN, committer=BOT)

    assert sha == _git(repo, "rev-parse", "HEAD").strip()


def test_a_rewrite_with_the_same_bytes_is_nothing_to_commit(tmp_path: Path) -> None:
    """A replace-by-rename save of unchanged text leaves the file stat-dirty, not changed."""
    repo = _repo(tmp_path)
    _git(repo, "config", "diff.autoRefreshIndex", "false")
    tmp = repo / "seed.md.tmp"
    tmp.write_text("seed\n", encoding="utf-8")
    os.utime(tmp, (1_000_000_000, 1_000_000_000))
    tmp.replace(repo / "seed.md")

    assert git.commit_paths(repo, ["seed.md"], "noop", author=ROBIN, committer=BOT) is None
