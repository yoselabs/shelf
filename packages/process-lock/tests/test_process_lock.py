"""One process owns a path (moved from a2kay tests/core/test_owner_lock.py).

The holder runs in a second process: a ``flock`` taken twice in one process is re-entrant
by design, so only another process can be refused.
"""

from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest
from process_lock import LockHeldError, ProcessLock, held

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_HOLDER = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    from process_lock import ProcessLock
    lock = ProcessLock.acquire(Path(sys.argv[1]))
    print("READY", flush=True)
    sys.stdin.readline()
    """
)
_PROBE = "import sys\nfrom pathlib import Path\nfrom process_lock import ProcessLock\nProcessLock.acquire(Path(sys.argv[1]))\n"


def _hold(lock_path: Path) -> subprocess.Popen[str]:
    """A second process that holds the lock until its stdin closes."""
    holder = subprocess.Popen([sys.executable, "-c", _HOLDER, str(lock_path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert holder.stdout is not None
    assert holder.stdout.readline().strip() == "READY"
    return holder


def _release(holder: subprocess.Popen[str]) -> None:
    if holder.poll() is None:
        assert holder.stdin is not None
        holder.stdin.write("\n")
        holder.stdin.flush()
        holder.wait(timeout=10)


def _can_acquire_elsewhere(lock_path: Path) -> bool:
    return subprocess.run([sys.executable, "-c", _PROBE, str(lock_path)], capture_output=True, check=False).returncode == 0


@pytest.fixture
def holder(tmp_path: Path) -> Iterator[subprocess.Popen[str]]:
    proc = _hold(tmp_path / "owner.lock")
    try:
        yield proc
    finally:
        _release(proc)


def test_a_second_process_is_refused_with_the_holders_pid(tmp_path: Path, holder: subprocess.Popen[str]) -> None:
    with pytest.raises(LockHeldError) as caught:
        ProcessLock.acquire(tmp_path / "owner.lock")
    assert caught.value.pid == holder.pid
    assert caught.value.path == (tmp_path / "owner.lock").resolve()
    assert f"pid {holder.pid}" in str(caught.value)


def test_a_holder_that_wrote_no_pid_is_unknown(tmp_path: Path) -> None:
    """A lock held by something that wrote no pid still refuses, naming no pid."""
    path = tmp_path / "owner.lock"
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)  # a second descriptor: flock conflicts even in-process
        with pytest.raises(LockHeldError) as caught:
            ProcessLock.acquire(path)
        assert caught.value.pid is None
        assert "unknown process" in str(caught.value)
    finally:
        os.close(fd)


def test_a_killed_holder_leaves_no_lock(tmp_path: Path) -> None:
    proc = _hold(tmp_path / "owner.lock")
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait(timeout=10)

    lock = ProcessLock.acquire(tmp_path / "owner.lock")
    lock.release()


def test_one_process_may_take_it_twice_and_frees_it_at_the_last_release(tmp_path: Path) -> None:
    first = ProcessLock.acquire(tmp_path / "owner.lock")
    second = ProcessLock.acquire(tmp_path / "owner.lock")
    first.release()
    first.release()  # idempotent: one handle releases once
    assert not _can_acquire_elsewhere(tmp_path / "owner.lock")
    second.release()
    assert _can_acquire_elsewhere(tmp_path / "owner.lock")


def test_a_child_process_does_not_inherit_the_lock(tmp_path: Path) -> None:
    lock = ProcessLock.acquire(tmp_path / "owner.lock")
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], close_fds=False)
    try:
        lock.release()
        assert _can_acquire_elsewhere(tmp_path / "owner.lock"), "the sleeping child kept the lock"
    finally:
        child.kill()
        child.wait(timeout=10)


def test_held_names_what_this_process_holds(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "owner.lock"
    with ProcessLock.acquire(path) as lock:
        assert lock.path in held()
        assert (path.stat().st_mode & 0o777) == 0o600
        assert path.read_text(encoding="utf-8").strip() == str(os.getpid())
    assert lock.path not in held()
    lock.release()  # a released handle stays released


def test_a_failure_while_locking_closes_the_descriptor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_fd: int, _op: int) -> None:
        msg = "no locks here"
        raise OSError(msg)

    monkeypatch.setattr(fcntl, "flock", boom)
    with pytest.raises(OSError, match="no locks here"):
        ProcessLock.acquire(tmp_path / "owner.lock")
    assert not held()
