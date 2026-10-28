"""Real processes: a race for one lock, and a crash that leaves the descriptor behind."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import time
from typing import TYPE_CHECKING

import pytest
from process_lock import LockHeldError, ProcessLock, holder

if TYPE_CHECKING:
    from pathlib import Path

_RACER = textwrap.dedent(
    """
    import sys, time
    from pathlib import Path
    from process_lock import ProcessLock
    lock_path, log, name = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    with ProcessLock.acquire(lock_path, timeout=30, label=name):
        with log.open("a") as f:
            f.write(f"in {name}\\n"); f.flush()
            time.sleep(0.4)
            f.write(f"out {name}\\n")
    """
)

# Takes the lock, optionally forks a child (no exec) that keeps the descriptor, prints the child's pid.
_HOLDER = textwrap.dedent(
    """
    import os, sys, time
    from pathlib import Path
    from process_lock import ProcessLock
    ProcessLock.acquire(Path(sys.argv[1]))
    child = os.fork() if sys.argv[2] == "fork" else 0
    if child == 0 and sys.argv[2] == "fork":
        time.sleep(60)
        os._exit(0)
    print(child, flush=True)
    time.sleep(60)
    """
)


def _spawn_holder(path: Path, mode: str) -> tuple[subprocess.Popen[str], int]:
    proc = subprocess.Popen([sys.executable, "-c", _HOLDER, str(path), mode], stdout=subprocess.PIPE, text=True)
    assert proc.stdout is not None
    return proc, int(proc.stdout.readline())


def test_two_processes_racing_never_hold_the_lock_together(tmp_path: Path) -> None:
    log = tmp_path / "log"
    procs = [subprocess.Popen([sys.executable, "-c", _RACER, str(tmp_path / "r.lock"), str(log), name]) for name in ("a", "b")]
    assert [p.wait(timeout=60) for p in procs] == [0, 0]
    lines = log.read_text(encoding="utf-8").split()
    assert lines in (["in", "a", "out", "a", "in", "b", "out", "b"], ["in", "b", "out", "b", "in", "a", "out", "a"])


def test_a_sigkilled_holder_whose_forked_child_keeps_the_descriptor_stays_locked(tmp_path: Path) -> None:
    path = tmp_path / "crash.lock"
    proc, child = _spawn_holder(path, "fork")
    try:
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)
        began = time.monotonic()
        with pytest.raises(LockHeldError) as caught:
            ProcessLock.acquire(path, timeout=0.5)
        assert time.monotonic() - began >= 0.5
        assert str(caught.value).endswith(f"held by an inherited descriptor; recorded holder pid {proc.pid} is gone")
        assert caught.value.pid == proc.pid
        assert caught.value.holder is not None
        assert holder(path) == caught.value.holder  # nothing was broken or rewritten
    finally:
        os.kill(child, signal.SIGKILL)


def test_a_sigkilled_holder_with_no_inheritor_is_released_by_the_kernel(tmp_path: Path) -> None:
    path = tmp_path / "crash.lock"
    proc, _ = _spawn_holder(path, "alone")
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait(timeout=10)
    with ProcessLock.acquire(path) as lock:
        record = holder(lock.path)
        assert record is not None
        assert record.pid == os.getpid()
