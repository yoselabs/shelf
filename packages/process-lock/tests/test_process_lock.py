"""One process owns a path (moved from a2kay tests/core/test_owner_lock.py).

The holder runs in a second process: a ``flock`` taken twice in one process is re-entrant
by design, so only another process can be refused.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import os
import signal
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING, NoReturn

import process_lock
import pytest
from process_lock import LockHeldError, ProcessLock, held
from process_lock import holder as read_holder

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
    return subprocess.run([sys.executable, "-c", _PROBE, str(lock_path)], capture_output=True, check=False, timeout=10).returncode == 0


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
        record = read_holder(path)
        assert record is not None
        assert record.pid == os.getpid()
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


@pytest.mark.parametrize("failure", ["serialization", "write", "truncate", "registry", "interrupted"])
def test_failed_acquisition_does_not_keep_a_kernel_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    path = tmp_path / "failed.lock"
    descriptors: list[int] = []
    original_write = process_lock._write
    original_dumps = process_lock.json.dumps

    def recording_write(fd: int, record: dict[str, object]) -> None:
        descriptors.append(fd)
        if failure == "interrupted":
            raise KeyboardInterrupt
        original_write(fd, record)

    def serialize(value: object) -> str:
        if isinstance(value, dict) and "pid" in value:
            msg = "metadata serialization failed after flock"
            raise TypeError(msg)
        return original_dumps(value)

    def fail(*_args: object) -> NoReturn:
        msg = "metadata write failed after flock"
        raise OSError(msg)

    def fail_registry(*_args: object, **_kwargs: object) -> NoReturn:
        msg = "registry adoption failed"
        raise MemoryError(msg)

    expected_error = {"serialization": TypeError, "registry": MemoryError, "interrupted": KeyboardInterrupt}.get(failure, OSError)
    try:
        with monkeypatch.context() as fault:
            fault.setattr(process_lock, "_write", recording_write)
            if failure == "serialization":
                fault.setattr(process_lock.json, "dumps", serialize)
            elif failure == "registry":
                fault.setattr(process_lock, "_Held", fail_registry)
            elif failure != "interrupted":
                fault.setattr(process_lock.os, "pwrite" if failure == "write" else "ftruncate", fail)
            with pytest.raises(expected_error):
                ProcessLock.acquire(path, label="failed acquisition", meta={"task": "shelf-7c34"})
        assert path.resolve() not in held()
        assert _can_acquire_elsewhere(path), "failed acquisition retained an unregistered kernel lock"
        with pytest.raises(OSError) as closed:
            os.fstat(descriptors[0])
        assert closed.value.errno == errno.EBADF
    finally:
        for fd in descriptors:
            with contextlib.suppress(OSError):
                actual, expected = os.fstat(fd), path.stat()
                if (actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino):
                    os.close(fd)


def test_refused_holder_read_failure_closes_its_unregistered_descriptor(
    tmp_path: Path, holder: subprocess.Popen[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "owner.lock"
    descriptors: list[int] = []

    def unreadable(fd: int, _size: int, _offset: int) -> NoReturn:
        descriptors.append(fd)
        msg = "holder metadata unreadable"
        raise OSError(msg)

    try:
        with monkeypatch.context() as fault:
            fault.setattr(process_lock.os, "pread", unreadable)
            with pytest.raises(OSError, match="holder metadata unreadable"):
                ProcessLock.acquire(path)
        assert not _can_acquire_elsewhere(path), "metadata failure bypassed a live foreign holder"
        with pytest.raises(OSError) as closed:
            os.fstat(descriptors[0])
        assert closed.value.errno == errno.EBADF
        _release(holder)
        assert _can_acquire_elsewhere(path)
    finally:
        for fd in descriptors:
            with contextlib.suppress(OSError):
                actual, expected = os.fstat(fd), path.stat()
                if (actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino):
                    os.close(fd)
