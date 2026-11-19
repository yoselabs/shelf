"""`python -m any_gate test`: run the suites a plan lists that have not already passed, one box slot at a time.

The plan arrives on stdin, one suite per line: `path<TAB>key`. The path is what pytest is given; the key says what the suite's result
depends on (empty: never skip it). A suite whose key is in the receipts file already passed on exactly that input and is skipped. The rest
run in one `run_tests` under a lease, so gates started at once queue instead of thrashing the box; when they pass, each is recorded. Exit
0: green or nothing to run; 1: a test failed or a run was stopped; 2: usage. Notices go to the descriptor in `$GATE_NOTICE_FD` when open
(the gate's parallel runner points it at its terminal), else to stderr. The suite and its tests run through the language-neutral plan
and receipts formats; only the pytest stages are Python's.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from any_lease import Leases

from any_gate.receipts import Receipts
from any_gate.run import run_tests

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


def _show(line: str) -> None:
    sys.stdout.write(line)
    sys.stdout.flush()


def _lease_root(given: str | None) -> Path:
    if given:
        return Path(given)
    cache = os.environ.get("XDG_CACHE_HOME", "") or str(Path.home() / ".cache")
    return Path(os.environ.get("GATE_LEASE_ROOT") or Path(cache) / "gate-leases")


def _test(args: argparse.Namespace, stdin: TextIO) -> int:
    try:
        plan = parse_plan(stdin.read())
    except PlanError as err:
        notice(str(err))
        return 2
    receipts = Receipts(Path(args.receipts))
    todo = [(path, key) for path, key in plan if not (key and receipts.has(path, key))]
    if len(todo) < len(plan):
        notice(f"{len(plan) - len(todo)} suite(s) skipped, unchanged since they passed")
    if not todo:
        notice("nothing to run")
        return 0
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
        workers = None if args.workers == "auto" else int(args.workers)
        outcome = run_tests(
            [path for path, _ in todo],
            cwd=cwd,
            workers=workers,
            wall=args.wall,
            idle=args.idle,
            on_output=_show,
            extra=args.pytest_args,
        )
    stopped = [f"{stage.name} stopped by the {stage.stopped} limit" for stage in outcome.stages if stage.stopped]
    for line in stopped:
        notice(line)
    if outcome.quarantined_failed:
        notice("a quarantined test failed: reported, not blocking")
    if not outcome.ok:
        return 1
    for path, key in todo:
        if key:
            receipts.record(path, key)
    return 0


def main(argv: Sequence[str] | None = None, *, stdin: TextIO | None = None) -> int:
    parser = argparse.ArgumentParser(prog="any-gate", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    test = sub.add_parser("test", help="run the planned suites that have not passed on this input")
    test.add_argument("--receipts", required=True, help="the receipts file (JSON); suites recorded there are skipped")
    test.add_argument("--lease-root", help="the lease folder (default $GATE_LEASE_ROOT, else ~/.cache/gate-leases)")
    test.add_argument("--slots", type=int, default=1, help="runs allowed at once on this box (default 1)")
    test.add_argument("--workers", default="auto", help="pytest workers: a number, or auto (sized to the tests and the box)")
    test.add_argument("--wall", type=float, default=3600.0, help="seconds a stage may take before its tree is stopped")
    test.add_argument("--idle", type=float, default=600.0, help="seconds a stage may stay silent before its tree is stopped")
    test.add_argument("--cwd", default=".", help="where pytest runs (default: here)")
    test.add_argument("pytest_args", nargs=argparse.REMAINDER, metavar="-- PYTEST_ARGS", help="passed to every pytest stage")
    args = parser.parse_args(argv)
    args.pytest_args = args.pytest_args[1:] if args.pytest_args[:1] == ["--"] else args.pytest_args
    return _test(args, stdin if stdin is not None else sys.stdin)
