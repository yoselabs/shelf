"""Run a child process and measure what it cost: wall seconds and its own peak resident memory."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from any_speech.guard import MemoryBudgetError

if TYPE_CHECKING:
    import resource
    from collections.abc import Sequence
    from pathlib import Path

_GB = 1e9
_TAIL = 400
_WATCH_EVERY = 0.5  # seconds between reads of the group's memory; a `ps` call costs about 10 ms
_KB = 1024.0


@dataclass(frozen=True, slots=True)
class ChildResult:
    returncode: int
    seconds: float
    peak_gb: float
    stderr_tail: str


class Runner(Protocol):
    def __call__(self, args: Sequence[str | Path], *, timeout: float | None, budget_gb: float | None) -> ChildResult: ...


def run_child(args: Sequence[str | Path], *, timeout: float | None, budget_gb: float | None = None) -> ChildResult:
    """Wait on this one child with wait4, so the memory figure is its own, not the largest of every child so far.

    The child runs in its own process group. With a budget, the group's resident memory is read every half second and
    the group is killed the moment it is over, so a runaway engine is stopped, not just reported afterwards.
    """
    # ru_maxrss is bytes on macOS, kilobytes elsewhere
    unit = 1.0 if os.uname().sysname == "Darwin" else 1024.0
    started = time.monotonic()
    with tempfile.TemporaryFile() as err, tempfile.TemporaryFile() as out:
        process = subprocess.Popen([str(a) for a in args], stdout=out, stderr=err, start_new_session=True)
        try:
            _, status, usage = _wait4(process, timeout, budget_gb)
        except (subprocess.TimeoutExpired, MemoryBudgetError):
            _kill_group(process.pid)
            process.wait()
            raise
        err.seek(0)
        tail = err.read()[-_TAIL:].decode("utf-8", "replace")
    return ChildResult(os.waitstatus_to_exitcode(status), time.monotonic() - started, usage.ru_maxrss * unit / _GB, tail)


def _wait4(process: subprocess.Popen[bytes], timeout: float | None, budget_gb: float | None) -> tuple[int, int, resource.struct_rusage]:
    deadline = None if timeout is None else time.monotonic() + timeout
    next_look = time.monotonic()
    while True:
        pid, status, usage = os.wait4(process.pid, os.WNOHANG)
        if pid:
            process.returncode = 0  # reaped here; Popen must not wait again
            return pid, status, usage
        if deadline is not None and time.monotonic() > deadline:
            raise subprocess.TimeoutExpired(str(process.args), timeout or 0.0)
        if budget_gb is not None and time.monotonic() >= next_look:
            next_look = time.monotonic() + _WATCH_EVERY
            used = _group_gb(process.pid)
            if used > budget_gb:
                message = f"child group is using {used:.2f} GB, over the {budget_gb:.2f} GB budget: killed"
                raise MemoryBudgetError(message)
        time.sleep(0.02)


def _kill_group(pgid: int) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pgid, signal.SIGKILL)


def _group_gb(pgid: int) -> float:
    """Resident memory of every process in the group, from `ps` (the same call on macOS and Linux)."""
    listing = subprocess.run(["ps", "-A", "-o", "pgid=,rss="], capture_output=True, text=True, check=False).stdout
    total_kb = 0
    for line in listing.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == str(pgid):
            total_kb += int(parts[1])
    return total_kb * _KB / 1e9
