"""The ambient environment is injected: a snapshot is taken once by the caller, the library never reads the process environment."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from git_porcelain import GitError, GitUnavailable, RealRepo, run_git, sync_status
from git_porcelain.testing import git

if TYPE_CHECKING:
    from pathlib import Path


def _marker(repo: RealRepo, cwd: Path) -> str:
    return repo.run(cwd, "config", "--get", "ambient.seen", check=False, pin=False).out.strip()


@pytest.fixture
def work(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    return tmp_path


def test_a_snapshot_is_taken_once_and_later_changes_do_not_reach_git(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = RealRepo(work, ambient=dict(os.environ))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "ambient.seen")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "yes")
    assert _marker(repo, work) == ""


def test_a_snapshot_still_strips_the_variables_that_aim_git_elsewhere(work: Path) -> None:
    other = work / "other"
    other.mkdir()
    git(other, "init", "-q")
    repo = RealRepo(work, ambient={**os.environ, "GIT_DIR": str(other / ".git")})
    assert repo.run(work, "rev-parse", "--show-toplevel", pin=False).out.strip() == str(work.resolve())


def test_a_snapshot_without_git_on_its_path_fails_loud(work: Path) -> None:
    repo = RealRepo(work, ambient={"PATH": str(work / "nowhere")})
    with pytest.raises(GitUnavailable, match="git not found"):
        repo.run(work, "status")


def test_the_path_functions_run_on_the_environment_they_are_given_not_the_process_one(work: Path) -> None:
    nowhere = {"PATH": str(work / "nowhere")}
    with pytest.raises(GitError, match="git not found"):
        run_git(work, "status", ambient=nowhere)
    with pytest.raises(GitError, match="git not found"):
        sync_status(work, ambient=nowhere)
