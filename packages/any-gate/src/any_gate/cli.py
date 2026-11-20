"""`python -m any_gate`: `test`, `changed`, `steps`, and the gate's state verbs `start`, `passed` and `pre-push`.

`steps [--runner just] STEP...` runs the gate's steps at once, each into its own log, then prints one timing line and the log of every step
that failed (see `any_gate.steps`); exit 1 when one failed. `$GATE_STEP_BUDGET` (default 60) and `$GATE_BUDGET` (default 180) are seconds.

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
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from any_lease import Leases

from any_gate import changed as changed_files
from any_gate.receipts import Receipts
from any_gate.runner import RunResult, run_runner
from any_gate.state import GateState, common_dir
from any_gate.steps import GATE_BUDGET, STEP_BUDGET, run_and_report

if TYPE_CHECKING:
    from collections.abc import Sequence

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
    shared = common_dir(repo)
    return Receipts(shared / "gate-receipts.json") if shared else None


def _show(line: str) -> None:
    sys.stdout.write(line)
    sys.stdout.flush()


def _lease_root(given: str | None) -> Path:
    if given:
        return Path(given)
    cache = os.environ.get("XDG_CACHE_HOME", "") or str(Path.home() / ".cache")
    return Path(os.environ.get("GATE_LEASE_ROOT") or Path(cache) / "gate-leases")


def _run_under_lease(args: argparse.Namespace, units: list[str]) -> RunResult:
    """Queue for a test slot, saying who holds it, then run `units` through the runner while holding it."""
    cwd = Path(args.cwd).resolve()
    said = False

    def waiting(wait: Waiting) -> None:
        nonlocal said
        if not said:
            said = True
            holder = wait.occupants[0].holder if wait.occupants else None
            notice(f"waiting for a test slot, held by {(holder.label if holder else None) or 'an unnamed run'}")

    with Leases(_lease_root(args.lease_root)).acquire(LEASE_NAME, args.slots, label=f"gate in {cwd}", on_wait=waiting) as held:
        if held.waited >= 1:
            notice(f"got a test slot after {held.waited:.0f}s")
        return run_runner(args.runner, units, cwd=cwd, wall=args.wall, idle=args.idle, on_output=_show)


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
    todo = [(path, key) for path, key in plan if not (key and receipts.has(path, key))]
    if len(todo) < len(plan):
        notice(f"{len(plan) - len(todo)} suite(s) skipped, unchanged since they passed")
    if not todo:
        notice("nothing to run")
        return 0
    outcome = _run_under_lease(args, [path for path, _ in todo])
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


def _steps(args: argparse.Namespace) -> int:
    return run_and_report(args.names, runner=args.runner, step_budget=args.step_budget, gate_budget=args.gate_budget, say=_say)


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
        if receipts is not None and GateState(repo, receipts).green(args.gate):
            notice(f"tree already passed `{args.gate}`; not run again")
            return 0
        return _exec(cmd)
    if receipts is None:  # outside a git repo nothing is noted and nothing is recorded
        return 0
    gate = GateState(repo, receipts)
    if args.command == "start":
        gate.start()
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
    ):
        sp = sub.add_parser(verb, help=help_text)
        sp.add_argument("--repo", default=".", help="the repo (default: here)")
        sp.add_argument("--receipts", help="the receipts file (default: gate-receipts.json in the git directory)")
        if verb != "start":
            sp.add_argument("--gate", default="check", help="the gate (default: check)")
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
