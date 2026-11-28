"""Run a stack's test runner on the units a plan left, under a wall and an idle limit.

The core does not know what a unit is or how its tests run. A runner is any command that takes the units as its last arguments and exits 0
when they are green (the Python adapter's is `python -m any_gate_python run`, a .NET one would wrap `dotnet test`). A limit stops the whole
process tree (stream-proc), so a hung test cannot hold the box.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from stream_proc import run as run_process

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

__all__ = ["RunResult", "run_runner"]


@dataclass(frozen=True)
class RunResult:
    """The runner's exit code (None when we stopped it), and why we stopped it (`wall`, `idle` or `stopped`), if we did."""

    returncode: int | None
    stopped: Literal["wall", "idle", "stopped"] | None

    @property
    def ok(self) -> bool:
        return self.stopped is None and self.returncode == 0


def run_runner(
    runner: Sequence[str],
    units: Sequence[str],
    *,
    cwd: Path,
    wall: float,
    idle: float,
    on_output: Callable[[str], None] | None = None,
    env: Mapping[str, str] | None = None,
) -> RunResult:
    """Run `runner UNIT...` in `cwd` with `env` (None: ours); its output lines (newline kept) go to `on_output`."""
    result = run_process([*runner, *units], cwd=cwd, env=env, on_stdout=on_output, on_stderr=on_output, timeout=wall, idle=idle)
    return RunResult(result.returncode, result.timed_out)
