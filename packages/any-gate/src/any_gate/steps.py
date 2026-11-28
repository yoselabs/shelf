"""The gate's steps at once: each into its own log, a failure shown the moment it lands, one line per step at the end.

A step is a recipe the runner (`just`) is asked to run by name; each name is a recipe, so the gate graph still reads its edges. Each runs
in a session of its own (`stream_proc.run`), so a step that hangs past `step_limit` has its whole process tree stopped, and a Ctrl-C stops
every tree instead of orphaning it. A step's output goes to its log. A notice it must show now (a test slot's "waiting") goes to the
terminal through the descriptor named in `GATE_NOTICE_FD`, which the runner passes on. A step that fails prints the head and the tail of
its log at once (10 + 10 lines, each cut at 200 characters) and the path of the copy kept in `<git-dir>/gate-logs/<step>.log`, while the
others keep running (the default: a fix-one-rerun-find-the-next loop costs more than the seconds saved); with a `halt` event
(`--fail-fast`) the first failure stops the others' trees, and those steps are reported "not judged", never as passed.

Log-driven output, terse: a header `gate base=<ref> files=N: <steps>`, then after the steps one line per step, `ok|WARN|FAIL|stop NAME Ns |
<why it ran> | <the step's own note>`, a skipped step as `skipped NAME: <why>` (the prefix other tools scan for), and a footer
`gate FAIL a b | 4 ok 1 skipped | 41s`. A step reports what it did with `note("2/41 suites")` (one `gate-note: ` line in its log; the last
one counts); a step the gate said to run whose note starts `0 ` did nothing and is a WARN. A step over its budget is marked `⚠ over Ns`.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import stream_proc

from any_gate import changed
from any_gate import opens as step_opens
from any_gate.notice import announce
from any_gate.state import common_dir

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping, Sequence

STEP_BUDGET = 60.0
GATE_BUDGET = 180.0
STEP_LIMIT = 3600.0  # seconds before a step's tree is stopped: a hang guard (no repository has CI to kill it), not a budget
SKIPPED = "skipped "
NOTE = "gate-note: "
SHOWN_HEAD = 10
SHOWN_TAIL = 10
LINE_CAP = 200
TIMED_OUT = 124  # a step stopped at its limit
INTERNAL = 70  # the gate itself failed while running a step (an unreadable log, a callback that raised): never a pass


@dataclass(frozen=True)
class Step:
    """How one step ended: exit code (127 when the runner could not start), whole seconds taken, and its log.

    `stopped` says the gate stopped it because another step failed under --fail-fast: it judged nothing. A flag, not an exit code: a
    recipe may itself exit with any number (docker and xargs exit 125).
    """

    name: str
    returncode: int
    seconds: int
    log: str
    stopped: bool = False
    log_path: str = ""  # a failed step's log, kept past the run (`<git-dir>/gate-logs/<step>.log`)


@dataclass(frozen=True)
class Report:
    """All steps, and the whole gate's whole seconds."""

    steps: tuple[Step, ...]
    total: int

    @property
    def failed(self) -> tuple[Step, ...]:
        return tuple(step for step in self.steps if step.returncode != 0 and not step.stopped)

    @property
    def not_judged(self) -> tuple[Step, ...]:
        return tuple(step for step in self.steps if step.stopped)


def note(text: str) -> None:
    """Say, in one line, what this step did (`note("2/41 suites")`): the gate prints it on the step's line; `0 ...` raises a WARN."""
    sys.stdout.write(f"{NOTE}{text}\n")
    sys.stdout.flush()


def _note_of(step: Step) -> str:
    found = [line[len(NOTE) :].strip() for line in step.log.splitlines() if line.startswith(NOTE)]
    return found[-1] if found else ""


def _keep(name: str, text: str, cwd: Path | None, env: Mapping[str, str]) -> str:
    """Write a failed step's log where it survives the run; the path, or "" when nothing could be written."""
    shared = common_dir(cwd or Path.cwd(), env)
    folder = (shared / "gate-logs") if shared else Path(tempfile.gettempdir()) / "any-gate-logs"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}.log"
        path.write_text(text, encoding="utf-8")
    except OSError:
        return ""
    return str(path)


def _run_step(
    name: str, log: Path, *, runner: str, cwd: Path | None, env: Mapping[str, str], tty: int, limit: float, stop: threading.Event
) -> tuple[int, bool]:
    """Run `runner name` in a session of its own into `log`; its exit code (see `_code`) and whether the gate stopped it."""
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
            return 127, False
        if done.timed_out == "wall":
            write(f"gate: {name} ran over its {limit:g}s limit; its process tree was stopped\n")
        if done.survivors:
            write(f"gate: {name}: processes left running after the stop: {' '.join(map(str, done.survivors))}\n")
        return _code(done), done.timed_out in ("stopped", "idle")


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
    opens: Path | None = None,
) -> Report:
    """Run `runner NAME` for every name at once in `env`; `terminal` is the descriptor notices go to (default: a copy of stderr).

    A name in `skip` is never started: its step is a pass whose log is the reason (a `skipped ...` line). `on_done` hears each step
    that failed, the moment it ends (under a lock: one call at a time). A step over `step_limit` seconds has its tree stopped (exit 124).
    With `opens` (a folder) every step runs with the open counter of `any_gate.opens` and writes its counts there.
    With a `halt` event the first failure sets it and every running step's tree is stopped (fail-fast); without one the others finish.
    """
    own = terminal is None
    tty = os.dup(2) if own else terminal
    child_env = announce(env, tty)
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
            started = time.monotonic()
            try:
                log = Path(scratch) / f"{name}.log"
                step_env = child_env if opens is None else step_opens.env_for(name, opens, child_env)
                code, stopped = _run_step(name, log, runner=runner, cwd=cwd, env=step_env, tty=tty, limit=step_limit, stop=stopper)
                text = log.read_text(errors="replace")  # lossy-ok: display
                kept = _keep(name, text, cwd, env) if code != 0 and not stopped else ""
                step = Step(name, code, int(time.monotonic() - started), text, stopped, kept)
            except Exception as err:  # noqa: BLE001 -- the gate's own failure becomes a failed step: a lost step must never read as a pass
                step = Step(name, INTERNAL, int(time.monotonic() - started), f"gate: internal error running {name}: {err!r}\n")
            results[name] = step
            if step.returncode == 0 or step.stopped:
                return
            if halt is not None:
                halt.set()
            if on_done is not None:
                with heard:
                    on_done(step)

        _run_threads(names, one, stopper)
    if own:
        os.close(tty)
    return Report(tuple(results[name] for name in names), int(time.monotonic() - began))


def _run_threads(names: Sequence[str], one: Callable[[str], None], stopper: threading.Event) -> None:
    """Run `one(name)` in a thread per name and wait for all; on Ctrl-C, SIGTERM or a failed start set `stopper`, wait for every
    step that started to end, re-raise."""
    ended: list[threading.Event] = []

    def worker(name: str, flag: threading.Event) -> None:
        try:
            one(name)
        finally:
            flag.set()

    threads: list[threading.Thread] = []
    try:
        for name in names:
            flag = threading.Event()
            thread = threading.Thread(target=worker, args=(name, flag))
            thread.start()  # only a started thread gets waited for: its flag is registered after
            threads.append(thread)
            ended.append(flag)
        for thread in threads:
            thread.join()
    except BaseException:
        stopper.set()  # each step runs in a session of its own: the terminal's Ctrl-C does not reach them, so stop their trees
        for flag in ended:  # not join()/is_alive(): a join the signal interrupted reports its thread over while it still runs
            while not flag.wait(0.5):
                pass
        raise


def _code(done: stream_proc.Result) -> int:
    """The step's exit code: 124 at its limit, 128 + signal for a killed child (a stop by the gate reads as one)."""
    if done.timed_out == "wall":
        return TIMED_OUT
    if done.returncode is None:
        return 128 + (done.signal or 0)
    return done.returncode


FAILED_LOG_LINES = SHOWN_HEAD + SHOWN_TAIL  # lines of one failed step's log the gate prints: the head and the tail, the rest is in the log


def _cut(line: str) -> str:
    return line if len(line) <= LINE_CAP else line[: LINE_CAP - 1] + "…"


def failure_lines(step: Step) -> list[str]:
    """What a failed step shows: its name and seconds, the first 10 and last 10 lines of its log, and where the whole log is."""
    log = [_cut(line) for line in step.log.rstrip("\n").splitlines()]
    lines = [f"--- {step.name} ✗ {step.seconds}s"]
    if len(log) <= SHOWN_HEAD + SHOWN_TAIL:
        lines += log
    else:
        hidden = len(log) - SHOWN_HEAD - SHOWN_TAIL
        lines += [*log[:SHOWN_HEAD], f"... {hidden} more lines ...", *log[-SHOWN_TAIL:]]
    lines.append(f"log: {step.log_path}" if step.log_path else f"log: `just {step.name}` prints it again")
    return lines


def _reason(why: str, name: str) -> str:
    """The text after `run NAME: ` of an inputs reason."""
    return why.removeprefix(f"run {name}: ")


def _status(step: Step, why: str) -> str:
    if step.stopped:
        return "stop"
    if step.returncode != 0:
        return "FAIL"
    if why.startswith("run ") and _note_of(step).split(" ", 1)[0] == "0":
        return "WARN"  # the gate said run and the step did nothing: a green that judged nothing
    return "ok"


def render(
    report: Report, *, step_budget: float, gate_budget: float, shown: Collection[str] = (), why: Mapping[str, str] | None = None
) -> list[str]:
    """The lines the gate prints after its steps: one per step (a skipped one as its `skipped ...` line), the logs of failures not
    already `shown`, the budget warnings and the footer."""
    why = why or {}
    lines: list[str] = []
    counts = {"ok": 0, "skipped": 0, "WARN": 0, "FAIL": 0, "stop": 0}
    for step in report.steps:
        skip = next((line for line in step.log.splitlines() if line.startswith(SKIPPED)), None)
        if skip is not None and step.returncode == 0:
            lines.append(_cut(skip))
            counts["skipped"] += 1
            continue
        status = _status(step, why.get(step.name, ""))
        counts[status] += 1
        over = f" ⚠ over {step_budget:g}s" if step.seconds > step_budget else ""
        parts = [_reason(why.get(step.name, ""), step.name), _note_of(step)]
        if status == "FAIL":
            parts.append(f"log {step.log_path}" if step.log_path else "")
        detail = " | ".join(p for p in parts if p)
        lines.append(_cut(f"{status:<4} {step.name} {step.seconds}s{over}" + (f" | {detail}" if detail else "")))
    for step in report.failed:
        if step.name not in shown:
            lines += failure_lines(step)
    if report.total > gate_budget:
        lines.append(f"gate: ⚠ {report.total}s is over the {gate_budget:g}s gate budget: find the slow step above")
    if report.not_judged:
        lines.append(
            f"gate: not judged (stopped by --fail-fast, run without it to see them): {' '.join(s.name for s in report.not_judged)}"
        )
    verdict = "FAIL " + " ".join(step.name for step in report.failed) if report.failed else ("STOPPED" if report.not_judged else "ok")
    tally = " ".join(f"{n} {k}" for k, n in counts.items() if n)
    lines.append(f"gate {verdict} | {tally} | {report.total}s")
    return lines


def header(repo: Path, names: Sequence[str], why: Mapping[str, str] | None = None) -> str:
    """`gate base=<sha> files=N: a b c`: what the change set was measured against, so a gate that judged nothing shows `base=NONE`.

    Asks git again (4 calls): the reasons in `why` were computed by `inputs.explain`, which does not hand its change set on. `--all`
    asks nothing."""
    if why and all(text.endswith("--all") for text in why.values()):
        return f"gate base=- files=all: {' '.join(names)}"
    start = changed.base(repo)
    moved = changed.changed(repo) if start else None
    where = f"base={start[:7]} files={len(moved)}" if start and moved is not None else "base=NONE files=all"
    return f"gate {where}: {' '.join(names)}"


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
    opens: Path | None = None,
    why: Mapping[str, str] | None = None,
    hook: Path | None = None,
) -> int:
    """Run the steps, say each failure as it lands and the rest after; 0 when every step passed, else 1.

    `why` maps a step to the one line saying why it runs (`run test: 3 changed (*.py)`), shown on the step's line.

    With a `hook` folder (made by `opens.prepare`) the hook runs but nothing is printed (`reads` reads it afterwards).
    With an `opens` folder (made by `opens.prepare`) each step's file opens and process starts are counted and printed last.
    """
    say(header(cwd or Path.cwd(), names, why))
    shown: list[str] = []

    def land(step: Step) -> None:
        shown.append(step.name)
        for line in failure_lines(step):
            say(line)

    report = run_steps(
        names, env=env, runner=runner, cwd=cwd, skip=skip, step_limit=step_limit, halt=halt, on_done=land, opens=opens or hook
    )
    for line in render(report, step_budget=step_budget, gate_budget=gate_budget, shown=shown, why=why):
        say(line)
    if opens is not None:
        for line in step_opens.lines(step_opens.collect(opens, names)):
            say(line)
    return 1 if report.failed or report.not_judged else 0
