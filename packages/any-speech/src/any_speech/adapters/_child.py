"""Run a child process and measure what it cost: wall seconds and its own peak resident memory."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import resource
    from collections.abc import Sequence
    from pathlib import Path

_GB = 1e9
_TAIL = 400


@dataclass(frozen=True, slots=True)
class ChildResult:
    returncode: int
    seconds: float
    peak_gb: float
    stderr_tail: str


class Runner(Protocol):
    def __call__(self, args: Sequence[str | Path], *, timeout: float | None) -> ChildResult: ...


def run_child(args: Sequence[str | Path], *, timeout: float | None) -> ChildResult:
    """Wait on this one child with wait4, so the memory figure is its own, not the largest of every child so far."""
    # ru_maxrss is bytes on macOS, kilobytes elsewhere
    unit = 1.0 if os.uname().sysname == "Darwin" else 1024.0
    started = time.monotonic()
    with tempfile.TemporaryFile() as err, tempfile.TemporaryFile() as out:
        process = subprocess.Popen([str(a) for a in args], stdout=out, stderr=err)
        try:
            _, status, usage = _wait4(process, timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise
        err.seek(0)
        tail = err.read()[-_TAIL:].decode("utf-8", "replace")
    return ChildResult(os.waitstatus_to_exitcode(status), time.monotonic() - started, usage.ru_maxrss * unit / _GB, tail)


def _wait4(process: subprocess.Popen[bytes], timeout: float | None) -> tuple[int, int, resource.struct_rusage]:
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        pid, status, usage = os.wait4(process.pid, os.WNOHANG)
        if pid:
            process.returncode = 0  # reaped here; Popen must not wait again
            return pid, status, usage
        if deadline is not None and time.monotonic() > deadline:
            raise subprocess.TimeoutExpired(str(process.args), timeout or 0.0)
        time.sleep(0.02)
