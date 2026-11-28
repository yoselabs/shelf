"""`python -m any_gate`: `test`, `changed`, `steps`, and the gate's state verbs `start`, `passed` and `pre-push`.

`steps [--runner just] [--fail-fast] [--step-limit S] STEP...` runs the gate's steps at once, each into its own log, shows a failed
step's log the moment it ends, then prints one timing line (see `any_gate.steps`); exit 1 when one failed.
`--opens` prints, after the timing line, the file opens and process starts each step's Python processes made (`any_gate.opens`).
`--reads` judges each step's declared inputs against the files its Python processes read, and says what it cannot see (`any_gate.reads`);
exit 1 when a step reads a file its inputs omit. Use it with `--all`, so no step is skipped unjudged.
`$GATE_STEP_BUDGET` (default 60) and `$GATE_BUDGET` (default 180) are seconds.

A step that declares its input files in `gate-inputs.toml` and whose inputs did not change is not started (`any_gate.inputs`);
`--all` runs every step. So does a clean tree no gate has passed (a fresh clone, a merge, a reset: nothing "changed", so nothing was
judged). `$GATE_FAIL_FAST` set is `--fail-fast`. SIGTERM and SIGHUP stop every step's tree, as Ctrl-C does.

`changed [--scope all] [--config FILE]... [--not GLOB]... GLOB...` prints the files a per-file linter must check, NUL-separated
(`xargs -0`): those changed against the upstream merge-base matching a glob, or every matching file when `--scope all`, a `--config` file
changed, or there is no base (see `any_gate.changed`).

`start`, `passed --gate NAME` and `pre-push --gate NAME -- CMD...` keep a record of the trees a gate passed (see `any_gate.state`), so a
push does not run the gate again on the exact content that just passed it. `pre-push` skips CMD only when the tree is clean, HEAD is what
is pushed (`PRE_COMMIT_TO_REF`, when the hook runner gives it) and its key is recorded; anything else runs CMD in place of this process.
Outside a git repo `start` and `passed` do nothing and `pre-push` runs CMD.

`python -m any_gate test [OPTIONS] -- RUNNER...`: run the units a plan lists that have not already passed, one box slot at a time.

The plan arrives on stdin, one unit per line: `unit<TAB>key`. The unit is what the runner is given; the key says what its result
depends on (empty: never skip it). A unit whose key is in the receipts file already passed on exactly that input and is skipped. The rest
are passed to `RUNNER` (any command taking the units as its last arguments and exiting 0 when they are green) under a lease, so gates
started at once queue instead of thrashing the box; when it exits 0, each is recorded. Exit 0: green or nothing to run; 1: the runner
failed or was stopped by the wall or idle limit; 2: usage. Notices go to the descriptor in `$GATE_NOTICE_FD` when open (the gate's
parallel runner points it at its terminal), else to stderr. The core knows no language: the plan, the receipts and the runner contract
are all it uses.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from any_lease import Leases

from any_gate import changed as changed_files
from any_gate import inputs, reads
from any_gate import opens as step_opens
from any_gate.gate_lease import REPEAT_WAIT_NOTICE, WAIT_LIMIT, default_root, hold, wait_message
from any_gate.receipts import Receipts
from any_gate.runner import RunResult, run_runner
from any_gate.state import GateState, common_dir
from any_gate.steps import GATE_BUDGET, STEP_BUDGET, STEP_LIMIT, run_and_report

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from any_lease import Waiting

LEASE_NAME = "tests"


class PlanError(ValueError):
    """A plan line that is not `path` or `path<TAB>key`."""


def notice(text: str) -> None:
    """One line to `$GATE_NOTICE_FD` when that descriptor is open, else to stderr."""
    line = f"any-gate: {text}\n".encode()
    fd = os.environ.get("GATE_NOTICE_FD", "")
    if fd.isdigit():
        try:
            os.write(int(fd), line)
        except OSError:
            pass
        else:
            return
    sys.stderr.buffer.write(line)
    sys.stderr.flush()


def parse_plan(text: str) -> list[tuple[str, str]]:
    """`(path, key)` for each non-empty line; the key is empty when the line has none."""
    plan: list[tuple[str, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) > 2:
            message = f"plan line {number} has {len(fields)} fields, want path or path<TAB>key"
            raise PlanError(message)
        plan.append((fields[0], fields[1] if len(fields) == 2 else ""))
    return plan


def _receipts(given: str | None, repo: Path) -> Receipts | None:
    """The receipts file named, else `gate-receipts.json` in the git directory every worktree of `repo` shares; None outside a repo."""
    if given:
        return Receipts(Path(given))
    shared = common_dir(repo, os.environ)
    return Receipts(shared / "gate-receipts.json") if shared else None


def _show(line: str) -> None:
    sys.stdout.write(line)
    sys.stdout.flush()


def _lease_root(given: str | None) -> Path:
    if given:
        return Path(given)
    return default_root(os.environ)


def _run_under_lease(args: argparse.Namespace, left: Callable[[], list[tuple[str, str]]]) -> tuple[list[tuple[str, str]], RunResult | None]:
    """Queue for a test slot, saying who holds it; then ask `left` again, since the holder may have passed suites meanwhile, and run those.

    Returns the units run and the runner's result; no result when nothing was left once the slot came."""
    cwd = Path(args.cwd).resolve()
    told = -1.0

    def waiting(wait: Waiting) -> None:
        nonlocal told
        if told < 0 or wait.elapsed - told >= REPEAT_WAIT_NOTICE:
            told = wait.elapsed
            notice(wait_message(wait))

    with Leases(_lease_root(args.lease_root)).acquire(LEASE_NAME, args.slots, label=f"gate in {cwd}", on_wait=waiting) as held:
        if held.waited >= 1:
            notice(f"got a test slot after {held.waited:.0f}s")
        todo = left()
        if not todo:
            return todo, None
        # `$GATE_NOTICE_FD` names a descriptor of this process only: in the runner's tree that number is some other pipe (an xdist worker's
        # link to its controller), and a notice written to it corrupts that link and hangs the run.
        env = {name: value for name, value in os.environ.items() if name != "GATE_NOTICE_FD"}
        return todo, run_runner(args.runner, [path for path, _ in todo], cwd=cwd, wall=args.wall, idle=args.idle, on_output=_show, env=env)


def _test(args: argparse.Namespace, stdin: TextIO) -> int:
    if not args.runner:
        notice("test: give the runner command after --")
        return 2
    try:
        plan = parse_plan(stdin.read())
    except PlanError as err:
        notice(str(err))
        return 2
    receipts = _receipts(args.receipts, Path(args.cwd).resolve())
    if receipts is None:
        notice("not in a git repository: give --receipts")
        return 2
    if not plan:  # the gate said run, and nothing was planned: nothing is judged, so no green record
        notice("test: the plan holds 0 suites: nothing judged, so this run records no pass")
        GateState(Path(args.cwd).resolve(), receipts, os.environ).unjudged("test planned 0 suites")
    return _run_planned(args, plan, receipts)


def _run_planned(args: argparse.Namespace, plan: list[tuple[str, str]], receipts: Receipts) -> int:
    """Run the suites of `plan` that have no receipt, and record them when they pass."""
    reported = 0

    def left() -> list[tuple[str, str]]:
        nonlocal reported
        todo = [(path, key) for path, key in plan if not (key and receipts.has(path, key))]
        if len(plan) - len(todo) > reported:
            reported = len(plan) - len(todo)
            notice(f"{reported} suite(s) skipped, unchanged since they passed")
        return todo

    if not left():  # nothing to run: no reason to queue
        notice("nothing to run")
        return 0
    began = time.monotonic()
    todo, outcome = _run_under_lease(args, left)
    if outcome is None:
        notice("nothing to run")
        return 0
    skipped, secs = len(plan) - len(todo), time.monotonic() - began
    notice(f"test: ran {len(todo)} of {len(plan)} suite(s), {skipped} unchanged since they passed -- {secs:.0f}s")
    if outcome.stopped:
        notice(f"the runner was stopped by the {outcome.stopped} limit")
    if not outcome.ok:
        return 1
    for path, key in todo:
        if key:
            receipts.record(path, key)
    return 0


def _changed(args: argparse.Namespace) -> int:
    files = changed_files.select(Path(args.repo).resolve(), args.patterns, args.config, skip=args.skip, scope=args.scope)
    sys.stdout.write("".join(f"{path}\0" for path in files))
    return 0


def _say(line: str) -> None:
    sys.stderr.write(f"{line}\n")
    sys.stderr.flush()


def _stop_on_signal(_number: int, _frame: object) -> None:
    """SIGTERM and SIGHUP end the gate the way Ctrl-C does: every step's tree is stopped, none orphaned."""
    raise KeyboardInterrupt


def _decide(args: argparse.Namespace, repo: Path) -> tuple[dict[str, str], dict[str, str]]:
    """`(skips, runs)` for the steps: those not to start (see `inputs.explain`) and why each other one runs; all run under --all."""
    if args.all:
        return {}, {name: f"run {name}: --all" for name in args.names}

    def recorded() -> bool:
        receipts = _receipts(None, repo)
        return receipts is not None and GateState(repo, receipts, os.environ).green("check")

    return inputs.explain(repo, args.names, recorded)


def _steps(args: argparse.Namespace) -> int:
    fail_fast = args.fail_fast or os.environ.get("GATE_FAIL_FAST", "").lower() not in ("", "0", "false", "no")
    if len(set(args.names)) != len(args.names):
        notice("steps: a step is named twice")
        return 2
    if fail_fast and args.all:
        notice("steps: --fail-fast and --all do not mix: the release gate shows every failure")
        return 2
    for number in (signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(number, _stop_on_signal)
        except ValueError:  # not the main thread: the caller owns signals
            break
    repo = Path(args.repo).resolve()
    with (
        hold(
            _lease_root(args.lease_root),
            slots=args.gate_slots,
            wait_limit=args.gate_wait,
            label=f"gate in {repo}",
            env=os.environ,
            say=_say,
        ) as env,
        tempfile.TemporaryDirectory() as folder,
    ):
        skip, why = _decide(args, repo)  # after the wait: what changed while queued is judged too
        counted = step_opens.prepare(Path(folder)) if args.opens or args.reads else None
        step_env = {**env, "GATE_READS_ROOT": reads.root_env(repo)} if args.reads else env
        code = run_and_report(
            args.names,
            env=step_env,
            runner=args.runner,
            step_budget=args.step_budget,
            gate_budget=args.gate_budget,
            say=_say,
            skip=skip,
            why=why,
            step_limit=args.step_limit,
            halt=threading.Event() if fail_fast else None,
            opens=counted,
            show_opens=args.opens,
        )
        if args.reads and counted is not None:
            report, under = reads.audit(repo, [n for n in args.names if n not in skip], counted, args.runner)
            for line in report:
                _say(line)
            return 1 if under else code
        return code


def _exec(cmd: Sequence[str]) -> int:
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        os.execvpe(cmd[0], list(cmd), dict(os.environ))  # noqa: S606 -- running the gate's own command is this verb's job
    except OSError as err:
        notice(f"cannot run {cmd[0]}: {err}")
        return 127


def _state(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    receipts = _receipts(args.receipts, repo)
    if args.command == "pre-push":
        cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
        if not cmd:
            notice("pre-push: give the command after --")
            return 2
        if receipts is not None and GateState(repo, receipts, os.environ).green(args.gate):
            notice(f"tree already passed `{args.gate}`; not run again")
            return 0
        return _exec(cmd)
    if receipts is None:  # outside a git repo nothing is noted and nothing is recorded
        return 0
    gate = GateState(repo, receipts, os.environ)
    if args.command == "start":
        gate.start()
    elif args.command == "unjudged":
        gate.unjudged(args.reason)
    elif (reason := gate.unjudged_reason()) is not None:
        gate.passed(args.gate)
        notice(f"judged nothing ({reason}): nothing recorded for `{args.gate}`")
    elif not gate.passed(args.gate):
        notice(f"the tree did not stay as `start` noted it, or no start was noted: nothing recorded for `{args.gate}`")
    return 0


def main(argv: Sequence[str] | None = None, *, stdin: TextIO | None = None) -> int:
    parser = argparse.ArgumentParser(prog="any-gate", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    test = sub.add_parser("test", help="run the planned suites that have not passed on this input")
    test.add_argument(
        "--receipts", help="the receipts file (JSON; default: gate-receipts.json in the git directory); recorded suites are skipped"
    )
    test.add_argument("--lease-root", help="the lease folder (default $GATE_LEASE_ROOT, else ~/.cache/gate-leases)")
    test.add_argument("--slots", type=int, default=1, help="runs allowed at once on this box (default 1)")
    test.add_argument("--wall", type=float, default=3600.0, help="seconds the runner may take before its tree is stopped")
    test.add_argument("--idle", type=float, default=600.0, help="seconds the runner may stay silent before its tree is stopped")
    test.add_argument("--cwd", default=".", help="where the runner runs (default: here)")
    test.add_argument("runner", nargs=argparse.REMAINDER, metavar="-- RUNNER", help="the command; the units are appended to it")
    for verb, help_text in (
        ("start", "note the working tree as a gate begins"),
        ("passed", "record the noted tree as green for a gate, if it is unchanged"),
        ("pre-push", "run CMD unless HEAD's tree is recorded green for the gate"),
        ("unjudged", "note that a step judged nothing: `passed` then records nothing"),
    ):
        sp = sub.add_parser(verb, help=help_text)
        sp.add_argument("--repo", default=".", help="the repo (default: here)")
        sp.add_argument("--receipts", help="the receipts file (default: gate-receipts.json in the git directory)")
        if verb in {"passed", "pre-push"}:
            sp.add_argument("--gate", default="check", help="the gate (default: check)")
        if verb == "unjudged":
            sp.add_argument("--reason", required=True, help="why nothing was judged")
        if verb == "pre-push":
            sp.add_argument("cmd", nargs=argparse.REMAINDER, metavar="-- CMD")
    ch = sub.add_parser("changed", help="print the files a per-file linter must check, NUL-separated")
    ch.add_argument("--repo", default=".", help="the repo (default: here)")
    ch.add_argument("--scope", choices=("changed", "all"), default="changed", help="`all` prints every matching file")
    ch.add_argument("--config", action="append", default=[], help="a file (or glob) whose change selects everything")
    ch.add_argument("--not", dest="skip", action="append", default=[], metavar="GLOB", help="never select a path matching this")
    ch.add_argument("patterns", nargs="+", metavar="GLOB")
    st = sub.add_parser("steps", help="run the gate's steps (recipes) at once, with one timing line and the log of each failure")
    st.add_argument("--runner", default="just", help="the command run as `RUNNER NAME` for each step (default: just)")
    st.add_argument(
        "--step-budget", type=float, default=float(os.environ.get("GATE_STEP_BUDGET") or STEP_BUDGET), help="seconds a step may take"
    )
    st.add_argument(
        "--gate-budget", type=float, default=float(os.environ.get("GATE_BUDGET") or GATE_BUDGET), help="seconds the gate may take"
    )
    st.add_argument(
        "--step-limit",
        type=float,
        default=float(os.environ.get("GATE_STEP_LIMIT") or STEP_LIMIT),
        help="seconds before a step's whole process tree is stopped (a hang guard; default 3600)",
    )
    st.add_argument("--fail-fast", action="store_true", help="on the first failure stop the other steps (reported as not judged)")
    st.add_argument(
        "--opens", action="store_true", help="count each step's file opens and process starts (python only; see any_gate.opens)"
    )
    st.add_argument(
        "--reads",
        action="store_true",
        help="judge each step's declared inputs against the files its python processes read (see any_gate.reads); exit 1 on UNDER",
    )
    st.add_argument(
        "--gate-slots",
        type=int,
        default=int(os.environ.get("GATE_SLOTS") or 1),
        help="gates allowed at once on this box (default $GATE_SLOTS, else 1; 0: no lease): a second gate waits",
    )
    st.add_argument(
        "--gate-wait",
        type=float,
        default=float(os.environ.get("GATE_WAIT") or WAIT_LIMIT),
        help="seconds between re-judging a live holder; dead or stale ($GATE_STALE_AFTER, 7200s) ones are overridden",
    )
    st.add_argument("--lease-root", help="the lease folder (default $GATE_LEASE_ROOT, else ~/.cache/gate-leases)")
    st.add_argument("--all", action="store_true", help="run every step, whatever changed (the release gate)")
    st.add_argument("--repo", default=".", help="the repo whose gate-inputs.toml and changes decide what is skipped")
    st.add_argument("names", nargs="+", metavar="STEP")
    args = parser.parse_args(argv)
    if args.command == "steps":
        return _steps(args)
    if args.command == "changed":
        return _changed(args)
    if args.command != "test":
        return _state(args)
    args.runner = args.runner[1:] if args.runner[:1] == ["--"] else args.runner
    return _test(args, stdin if stdin is not None else sys.stdin)
