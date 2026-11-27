"""any_proc.testing: a child a test starts does not outlive the test process (ported from a2kay's tests/test_children.py)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import time
from typing import TYPE_CHECKING

from any_proc.testing import kill_group, start_child
from stream_proc import group_alive

# A child that itself starts a child, as a server does.
if TYPE_CHECKING:
    from collections.abc import Callable

_CHILD = "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)']); time.sleep(300)"

_STAND_IN = textwrap.dedent(
    f"""
    import sys
    from any_proc.testing import start_child
    child = start_child([sys.executable, "-c", {_CHILD!r}])
    print(child.pid, flush=True)
    sys.stdin.readline()
    """
)


def _group_pids(pgid: int) -> list[int]:
    out = subprocess.run(["ps", "-A", "-o", "pid=,pgid="], capture_output=True, text=True, check=True).stdout
    return [int(p) for p, g in (line.split() for line in out.splitlines()) if int(g) == pgid]


def _wait_for(done: Callable[[], bool], seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while not done() and time.monotonic() < deadline:
        time.sleep(0.05)


def _runner(*flags: str) -> tuple[subprocess.Popen[str], int]:
    runner = subprocess.Popen([sys.executable, *flags, "-c", _STAND_IN], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert runner.stdout is not None
    child = int(runner.stdout.readline())
    # The grandchild starts: waited for, not slept on, so a loaded box only makes it slower.
    _wait_for(lambda: len(_group_pids(child)) >= 2, 30)
    assert len(_group_pids(child)) >= 2
    return runner, child


def _close(runner: subprocess.Popen[str]) -> None:
    runner.wait()
    for pipe in (runner.stdin, runner.stdout):
        if pipe is not None:
            pipe.close()


def test_a_sigkilled_test_process_leaves_no_child_or_grandchild() -> None:
    runner, child = _runner()
    runner.send_signal(signal.SIGKILL)  # no finalizer runs
    _close(runner)
    _wait_for(lambda: not _group_pids(child), 6)
    assert _group_pids(child) == []


def test_a_test_process_that_exits_normally_leaves_nothing_and_no_resource_warning() -> None:
    runner, child = _runner("-W", "error")
    assert runner.stdin is not None
    runner.stdin.write("\n")
    runner.stdin.flush()
    _close(runner)
    assert runner.returncode == 0  # a ResourceWarning under -W error would fail the exit
    _wait_for(lambda: not _group_pids(child), 6)
    assert _group_pids(child) == []


def test_kill_group_stops_the_child_its_grandchild_and_its_watcher() -> None:
    child = start_child([sys.executable, "-c", _CHILD])
    _wait_for(lambda: len(_group_pids(child.pid)) >= 2, 30)
    assert group_alive(child.pid)
    kill_group(child, grace=2.0)
    assert child.poll() is not None
    assert not group_alive(child.pid)
    assert os.getpgid(os.getpid()) != child.pid  # the test's own group was never touched
