"""Run a child process and measure what it cost: wall seconds and its own peak resident memory."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from stream_proc import group_rss, popen_held, stop_tree

from any_speech.guard import MemoryBudgetError

if TYPE_CHECKING:
    import resource
    from collections.abc import Sequence
    from pathlib import Path

_GB = 1e9
_TAIL = 400
_WATCH_EVERY = 0.5  # seconds between reads of the group's memory
_GRACE = 1.0  # seconds a stopped engine gets after SIGTERM before SIGKILL


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

    The child runs in its own process group. With a budget, the group's resident memory is read every half second
    (stream-proc's process table) and the tree is stopped the moment it is over, so a runaway engine is stopped, not
    just reported afterwards.

    This is the one spawn that stays outside `stream_proc.capture`: only `os.wait4` returns the child's own peak
    (`ru_maxrss`), and `capture` reaps the child itself and discards it. So the spawn (own session, output to temp
    files), the wait4 loop and the mid-run budget check live here; the stop is stream-proc's `stop_tree`.
    Runs on a worker thread (`any_pipeline.blocking`), so its short `time.sleep` poll never blocks an event loop.
    """
    # ru_maxrss is bytes on macOS, kilobytes elsewhere: the one platform read the peak figure needs
    unit = 1.0 if os.uname().sysname == "Darwin" else 1024.0
    started = time.monotonic()
    with tempfile.TemporaryFile() as err, tempfile.TemporaryFile() as out:
        process, hold = popen_held([str(a) for a in args], stdout=out, stderr=err, start_new_session=True)
        try:
            hold.replay()
            _, status, usage = _wait4(process, timeout, budget_gb)
        except BaseException:
            stop_tree(process, grace=_GRACE)
            raise
        err.seek(0)
        # lossy-ok: display: a child's stderr tail goes into an error message
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


def _group_gb(pgid: int) -> float:
    """Resident memory of every process in the group, from stream-proc's process table (the same on macOS and Linux)."""
    return group_rss(pgid) / _GB
