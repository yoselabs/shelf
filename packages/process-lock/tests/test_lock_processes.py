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

# Takes the lock, then hands the open descriptor to a long-lived child: the lock outlives the holder.
_LEAKER = textwrap.dedent(
    """
    import subprocess, sys
    from pathlib import Path
    import process_lock
    path = Path(sys.argv[1]).resolve()
    process_lock.ProcessLock.acquire(path)
    fd = process_lock._REGISTRY[path].fd
    child = subprocess.Popen(["sleep", "60"], pass_fds=(fd,))
    print(child.pid, flush=True)
    sys.stdin.readline()
    """
)


def test_two_processes_racing_never_hold_the_lock_together(tmp_path: Path) -> None:
    log = tmp_path / "log"
    procs = [subprocess.Popen([sys.executable, "-c", _RACER, str(tmp_path / "r.lock"), str(log), name]) for name in ("a", "b")]
    assert [p.wait(timeout=60) for p in procs] == [0, 0]
    lines = log.read_text(encoding="utf-8").split()
    assert lines in (["in", "a", "out", "a", "in", "b", "out", "b"], ["in", "b", "out", "b", "in", "a", "out", "a"])


def test_a_sigkilled_holder_whose_descriptor_lives_on_is_broken_as_stale(tmp_path: Path) -> None:
    path = tmp_path / "crash.lock"
    holder_proc = subprocess.Popen([sys.executable, "-c", _LEAKER, str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert holder_proc.stdout is not None
    child_pid = int(holder_proc.stdout.readline())
    try:
        with pytest.raises(LockHeldError):
            ProcessLock.acquire(path, break_stale=False)  # still flock-held through the child
        os.kill(holder_proc.pid, signal.SIGKILL)
        holder_proc.wait(timeout=10)
        dead = holder(path)
        assert dead is not None
        assert dead.pid == holder_proc.pid
        assert dead.is_stale()

        began = time.monotonic()
        with ProcessLock.acquire(path, timeout=5) as lock:
            assert time.monotonic() - began < 5
            record = holder(lock.path)
            assert record is not None
            assert record.pid == os.getpid()
    finally:
        os.kill(child_pid, signal.SIGKILL)
        holder_proc.wait(timeout=10)
