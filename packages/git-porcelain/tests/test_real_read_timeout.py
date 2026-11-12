"""A bounded Git read that blocks (a writerless FIFO where Git opens a file) ends as ``GitTimeout``."""

from __future__ import annotations

import os
import subprocess
import time
from typing import TYPE_CHECKING

import pytest

from git_porcelain import GitTimeout, RealRepo, real_spawn
from git_porcelain.real_reads import is_read
from git_porcelain.testing import apply_hermetic_env, git

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def fifo_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    apply_hermetic_env(monkeypatch)
    git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("a")
    exclude = tmp_path / ".git" / "info" / "exclude"
    exclude.parent.mkdir(exist_ok=True)
    os.mkfifo(exclude)
    return tmp_path


def test_the_fifo_blocks_status_without_a_bound(fifo_repo: Path) -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(["git", "-C", str(fifo_repo), "status", "--porcelain"], check=False, capture_output=True, timeout=3)


def test_a_bounded_read_times_out_instead_of_hanging(fifo_repo: Path) -> None:
    repo = RealRepo(fifo_repo, read_timeout=2)
    with pytest.raises(GitTimeout, match=r"git status timed out after 2"):
        repo.run(fifo_repo, "status", "--porcelain")


def test_a_write_is_not_bounded_and_a_read_takes_no_optional_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    apply_hermetic_env(monkeypatch)
    repo = RealRepo(tmp_path, read_timeout=5)
    seen: list[tuple[float | None, str | None, bool]] = []

    def fake_run(
        argv: list[str], *, env: dict[str, str], timeout: float | None, stdin: bytes | None, group: bool
    ) -> subprocess.CompletedProcess[bytes]:
        seen.append((timeout, env.get("GIT_OPTIONAL_LOCKS"), group))
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(real_spawn, "run", fake_run)
    repo.run(tmp_path, "status", pin=False)
    repo.run(tmp_path, "commit", "-q", pin=False)
    assert seen == [(5, "0", True), (None, None, False)]


def _running(pid: int) -> bool:
    """Whether `pid` still runs (a zombie, waiting only for its parent to reap it, does not)."""
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], check=False, capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")


def test_a_timeout_kills_the_git_child_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`git status` runs the fsmonitor program as a child; one that blocks must not outlive the timeout."""
    apply_hermetic_env(monkeypatch)
    git(tmp_path, "init", "-q")
    pidfile = tmp_path / "pid"
    program = tmp_path / "monitor.sh"
    program.write_text(f"#!/bin/sh\necho $$ > '{pidfile}'\nexec sleep 60\n")
    program.chmod(0o755)
    git(tmp_path, "config", "core.fsmonitor", str(program))
    with pytest.raises(GitTimeout):
        RealRepo(tmp_path, read_timeout=2).run(tmp_path, "status", "--porcelain")
    child = int(pidfile.read_text())
    deadline = time.monotonic() + 5
    while _running(child) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _running(child)


@pytest.mark.parametrize(
    ("args", "read"),
    [
        (["status", "--porcelain"], True),
        (["--no-optional-locks", "status"], True),
        (["-c", "x=y", "diff", "--name-only"], True),
        (["worktree", "list", "--porcelain"], True),
        (["worktree", "add", "p"], False),
        (["commit", "-q"], False),
        (["add", "-A"], False),
        (["config", "k", "v"], False),
        (["checkout", "-q", "-f"], False),
    ],
)
def test_only_commands_that_read_are_bounded(args: list[str], read: bool) -> None:
    assert is_read(args) is read
