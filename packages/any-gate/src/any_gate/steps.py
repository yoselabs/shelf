"""The gate's steps at once: each into its own log, a failure shown the moment it lands, one timing line at the end.

A step is a recipe the runner (`just`) is asked to run by name; each name is a recipe, so the gate graph still reads its edges. Each runs
in a session of its own (`stream_proc.run`), so a step that hangs past `step_limit` has its whole process tree stopped, and a Ctrl-C stops
every tree instead of orphaning it. A step's output goes to its log. A notice it must show now (a test slot's "waiting") goes to the
terminal through the descriptor named in `GATE_NOTICE_FD`, which the runner passes on. A step that fails prints the head of its log at once,
while the others keep running (the default: a fix-one-rerun-find-the-next loop costs more than the seconds saved);
with a `halt` event (`--fail-fast`) the first failure stops the others' trees, and those steps are reported "not judged", never as
passed. After all steps ended: the `skipped ...` lines the steps printed,
one summary line with every step's seconds (a step over its budget marked `⚠ over Ns`, a
failed one `✗`, a stopped one `○`), a warning when the whole gate went over its budget, and the names that failed. The budgets are in
seconds: a slow step is a cost to see and fix, not to wait out.
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import stream_proc

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping, Sequence

STEP_BUDGET = 60.0
GATE_BUDGET = 180.0
STEP_LIMIT = 3600.0  # seconds before a step's tree is stopped: a hang guard (no repository has CI to kill it), not a budget
SKIPPED = "skipped "
TIMED_OUT = 124  # a step stopped at its limit
NOT_JUDGED = 125  # a step stopped because another failed under --fail-fast: it says nothing


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
        return tuple(step for step in self.steps if step.returncode not in (0, NOT_JUDGED))

    @property
    def not_judged(self) -> tuple[Step, ...]:
        return tuple(step for step in self.steps if step.returncode == NOT_JUDGED)


def _run_step(
    name: str, log: Path, *, runner: str, cwd: Path | None, env: Mapping[str, str], tty: int, limit: float, stop: threading.Event
) -> int:
    """Run `runner name` in a session of its own into `log`; its exit code (see `_code`)."""
    writing = threading.Lock()  # stdout and stderr arrive from two reader threads
    with log.open("w", encoding="utf-8", errors="replace") as sink:  # lossy-ok: display: a step's log is shown, never stored or hashed

        def write(line: str) -> None:
            with writing:
                sink.write(line)

        try:
            done = stream_proc.run(
                [runner, name], cwd=cwd, env=env, on_stdout=write, on_stderr=write, timeout=limit, stop=stop, pass_fds=(tty,)
            )
        except OSError as err:
            write(f"cannot run {runner}: {err}\n")
            return 127
        if done.timed_out == "wall":
            write(f"gate: {name} ran over its {limit:g}s limit; its process tree was stopped\n")
        return _code(done)


def run_steps(
    names: Sequence[str],
    *,
    env: Mapping[str, str],
    runner: str = "just",
    cwd: Path | None = None,
    terminal: int | None = None,
    skip: Mapping[str, str] | None = None,
    step_limit: float = STEP_LIMIT,
    halt: threading.Event | None = None,
    on_done: Callable[[Step], None] | None = None,
) -> Report:
    """Run `runner NAME` for every name at once in `env`; `terminal` is the descriptor notices go to (default: a copy of stderr).

    A name in `skip` is never started: its step is a pass whose log is the reason (a `skipped ...` line). `on_done` hears each step
    that failed, the moment it ends (under a lock: one call at a time). A step over `step_limit` seconds has its tree stopped (exit 124).
    With a `halt` event the first failure sets it and every running step's tree is stopped (fail-fast); without one the others finish.
    """
    own = terminal is None
    tty = os.dup(2) if own else terminal
    child_env = {**env, "GATE_NOTICE_FD": str(tty)}
    results: dict[str, Step] = {}
    skipped = dict(skip or {})
    began = time.monotonic()
    stopper = halt if halt is not None else threading.Event()  # a Ctrl-C sets it too, so every gate stops its trees
    heard = threading.Lock()
    with tempfile.TemporaryDirectory() as scratch:

        def one(name: str) -> None:
            if name in skipped:
                results[name] = Step(name, 0, 0, skipped[name] + "\n")
                return
            log = Path(scratch) / f"{name}.log"
            started = time.monotonic()
            code = _run_step(name, log, runner=runner, cwd=cwd, env=child_env, tty=tty, limit=step_limit, stop=stopper)
            step = Step(name, code, int(time.monotonic() - started), log.read_text(errors="replace"))  # lossy-ok: display: never stored
            results[name] = step
            if code in (0, NOT_JUDGED):
                return
            if halt is not None:
                halt.set()
            if on_done is not None:
                with heard:
                    on_done(step)

        threads = [threading.Thread(target=one, args=(name,)) for name in names]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            stopper.set()  # each step runs in a session of its own: the terminal's Ctrl-C does not reach them, so stop their trees
            for thread in threads:
                thread.join()
            raise
    if own:
        os.close(tty)
    return Report(tuple(results[name] for name in names), int(time.monotonic() - began))


def _code(done: stream_proc.Result) -> int:
    """The step's exit code: 124 at its limit, 125 when stopped by the gate, 128 + signal for a killed child."""
    if done.timed_out == "wall":
        return TIMED_OUT
    if done.timed_out is not None:
        return NOT_JUDGED
    if done.returncode is None:
        return 128 + (done.signal or 0)
    return done.returncode


FAILED_LOG_LINES = 60  # lines of one failed step's log the gate prints: the head names the failures, the rest is `just <step>` away


def failure_lines(step: Step) -> list[str]:
    """What a failed step shows: its name and seconds, then the head of its log (the rest is `just <step>` away)."""
    log = step.log.rstrip("\n").splitlines()
    lines = [f"--- {step.name} ✗ {step.seconds}s", *log[:FAILED_LOG_LINES]]
    if len(log) > FAILED_LOG_LINES:
        lines.append(f"... {len(log) - FAILED_LOG_LINES} more lines: `just {step.name}` prints them all")
    return lines


def render(report: Report, *, step_budget: float, gate_budget: float, shown: Collection[str] = ()) -> list[str]:
    """The lines the gate prints after its steps: skipped lines, the logs of failures not already `shown`, the timing line, the failures."""
    lines = [line for step in report.steps for line in step.log.splitlines() if line.startswith(SKIPPED)]
    for step in report.failed:
        if step.name not in shown:
            lines += failure_lines(step)
    cells = []
    for step in report.steps:
        mark = f" ⚠ over {step_budget:g}s" if step.seconds > step_budget else ""
        mark += " ○" if step.returncode == NOT_JUDGED else (" ✗" if step.returncode != 0 else "")
        cells.append(f"{step.name} {step.seconds}s{mark}")
    lines.append(f"gate: {' · '.join(cells)} -- total {report.total}s")
    if report.total > gate_budget:
        lines.append(f"gate: ⚠ {report.total}s is over the {gate_budget:g}s gate budget: find the slow step above")
    if report.failed:
        lines.append(f"gate: failed: {' '.join(step.name for step in report.failed)}")
    if report.not_judged:
        lines.append(
            f"gate: not judged (stopped by --fail-fast, run without it to see them): {' '.join(s.name for s in report.not_judged)}"
        )
    return lines


def run_and_report(
    names: Sequence[str],
    *,
    env: Mapping[str, str],
    runner: str,
    step_budget: float,
    gate_budget: float,
    say: Callable[[str], None],
    cwd: Path | None = None,
    skip: Mapping[str, str] | None = None,
    step_limit: float = STEP_LIMIT,
    halt: threading.Event | None = None,
) -> int:
    """Run the steps, say each failure as it lands and the rest after, and return 0 when every step passed, else 1."""
    say(f"gate: {' '.join(names)} (in parallel)")
    shown: list[str] = []

    def land(step: Step) -> None:
        shown.append(step.name)
        for line in failure_lines(step):
            say(line)

    report = run_steps(names, env=env, runner=runner, cwd=cwd, skip=skip, step_limit=step_limit, halt=halt, on_done=land)
    for line in render(report, step_budget=step_budget, gate_budget=gate_budget, shown=shown):
        say(line)
    return 1 if report.failed or report.not_judged else 0
