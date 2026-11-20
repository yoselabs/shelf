"""The gate's steps at once: each into its own log, one timing line, the log of every step that failed.

A step is a recipe the runner (`just`) is asked to run by name; each name is a recipe, so the gate graph still reads its edges. A step's
output goes to its log. A notice it must show now (a test slot's "waiting") goes to the terminal through the descriptor named in
`GATE_NOTICE_FD`, which the runner passes on. After all steps ended: the `skipped ...` lines the steps printed, the log of each failed step,
one summary line with every step's seconds (a step over its budget marked `⚠ over Ns`, a failed one `✗`), a warning when the whole gate went
over its budget, and the names that failed. The budgets are in seconds: a slow step is a cost to see and fix, not to wait out.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

STEP_BUDGET = 60.0
GATE_BUDGET = 180.0
SKIPPED = "skipped "


@dataclass(frozen=True)
class Step:
    """How one step ended: exit code (127 when the runner could not start), whole seconds taken, and its log."""

    name: str
    returncode: int
    seconds: int
    log: str


@dataclass(frozen=True)
class Report:
    """All steps, and the whole gate's whole seconds."""

    steps: tuple[Step, ...]
    total: int

    @property
    def failed(self) -> tuple[Step, ...]:
        return tuple(step for step in self.steps if step.returncode != 0)


def run_steps(names: Sequence[str], *, runner: str = "just", cwd: Path | None = None, terminal: int | None = None) -> Report:
    """Run `runner NAME` for every name at once; `terminal` is the descriptor notices go to (default: a copy of stderr)."""
    own = terminal is None
    tty = os.dup(2) if own else terminal
    env = {**os.environ, "GATE_NOTICE_FD": str(tty)}
    results: dict[str, Step] = {}
    began = time.monotonic()
    with tempfile.TemporaryDirectory() as scratch:

        def one(name: str) -> None:
            log = Path(scratch) / f"{name}.log"
            started = time.monotonic()
            with log.open("wb") as sink:
                try:
                    code = subprocess.run(
                        [runner, name], stdout=sink, stderr=subprocess.STDOUT, env=env, cwd=cwd, pass_fds=(tty,), check=False
                    ).returncode
                except OSError as err:
                    sink.write(f"cannot run {runner}: {err}\n".encode())
                    code = 127
            results[name] = Step(name, code, int(time.monotonic() - started), log.read_text(errors="replace"))

        threads = [threading.Thread(target=one, args=(name,)) for name in names]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    if own:
        os.close(tty)
    return Report(tuple(results[name] for name in names), int(time.monotonic() - began))


def render(report: Report, *, step_budget: float, gate_budget: float) -> list[str]:
    """The lines the gate prints after its steps: skipped lines, failed logs, the timing line, warnings, the failures."""
    lines = [line for step in report.steps for line in step.log.splitlines() if line.startswith(SKIPPED)]
    for step in report.failed:
        lines += [f"--- {step.name}", *step.log.rstrip("\n").splitlines()]
    cells = []
    for step in report.steps:
        mark = f" ⚠ over {step_budget:g}s" if step.seconds > step_budget else ""
        mark += " ✗" if step.returncode != 0 else ""
        cells.append(f"{step.name} {step.seconds}s{mark}")
    lines.append(f"gate: {' · '.join(cells)} -- total {report.total}s")
    if report.total > gate_budget:
        lines.append(f"gate: ⚠ {report.total}s is over the {gate_budget:g}s gate budget: find the slow step above")
    if report.failed:
        lines.append(f"gate: failed: {' '.join(step.name for step in report.failed)}")
    return lines


def run_and_report(
    names: Sequence[str], *, runner: str, step_budget: float, gate_budget: float, say: Callable[[str], None], cwd: Path | None = None
) -> int:
    """Run the steps, say what happened through `say`, and return 0 when every step passed, else 1."""
    say(f"gate: {' '.join(names)} (in parallel)")
    report = run_steps(names, runner=runner, cwd=cwd)
    for line in render(report, step_budget=step_budget, gate_budget=gate_budget):
        say(line)
    return 1 if report.failed else 0
