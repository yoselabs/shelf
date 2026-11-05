"""The ambient environment: a snapshot is taken once, no snapshot reads the process environment on every call."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from git_porcelain import GitUnavailable, RealRepo
from git_porcelain.testing import git

if TYPE_CHECKING:
    from pathlib import Path


def _marker(repo: RealRepo, cwd: Path) -> str:
    return repo.run(cwd, "config", "--get", "ambient.seen", check=False, pin=False).out.strip()


@pytest.fixture
def work(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    return tmp_path


def test_without_a_snapshot_a_changed_process_environment_is_honoured(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = RealRepo(work)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "ambient.seen")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "yes")
    assert _marker(repo, work) == "yes"


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
