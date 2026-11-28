"""`python -m any_gate_python`: `plan` names the package suites a change reaches; `run` is the pytest runner `any-gate test` calls.

`packages [--all]` prints the package directories the change reaches (the changed ones, their dependents, the lock read per package).

`plan [--plan] [--explain] [--reach N]` prints the pytest paths the change reaches, or with `--plan` one `path<TAB>key` per suite.

`run [--workers auto|N] [--wall S] [--idle S] [--nice N] [--pytest-args "ARGS"] PATH...` runs the paths in pytest stages (parallel, serial,
quarantine); exit 0 when none failed (a failing quarantined test is reported, not blocking), 1 otherwise.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
import tempfile
from pathlib import Path

from any_gate_python.compact import Compact
from any_gate_python.graph import lock_touched, workspace
from any_gate_python.select import affected, affected_packages, changed_files, everything, merge_base, plan, reach, wide_alarm
from any_gate_python.stages import run_tests


def _run(args: argparse.Namespace) -> int:
    def show(line: str) -> None:
        sys.stdout.write(line)
        sys.stdout.flush()

    compact: Compact | None = None
    if not os.environ.get("ANY_GATE_FULL"):
        folder = Path(tempfile.gettempdir()) / "any-gate-python"
        folder.mkdir(exist_ok=True)
        compact = Compact(show, folder / f"{Path.cwd().name}-last-test.log")

    workers = None if args.workers == "auto" else int(args.workers)
    outcome = run_tests(
        args.paths,
        cwd=Path.cwd(),
        workers=workers,
        env=os.environ,
        wall=args.wall,
        idle=args.idle,
        on_output=compact.feed if compact else show,
        extra=shlex.split(args.pytest_args),
        nice=args.nice,
    )
    if compact:
        compact.finish()
    for stage in outcome.stages:
        if stage.stopped:
            sys.stderr.write(f"any-gate-python: {stage.name} stage stopped by the {stage.stopped} limit\n")
    if outcome.quarantined_failed:
        sys.stderr.write("any-gate-python: a quarantined test failed: reported, not blocking\n")
    return 0 if outcome.ok else 1


def _lock(repo: Path) -> set[str] | None:
    """The packages the lock files changed for; None (every package) when there is no base to read them against."""
    start = merge_base(repo)
    return None if start is None else lock_touched(repo, start)


EXPLAIN_FILES = 5


def explain_line(changed: list[str] | None) -> str:
    """`affected: N changed file(s): a b c d e (+M more)`: the count and the first few, never a 20 KB line; None: the base is unknown."""
    if changed is None:
        return "affected: base unknown: every suite"
    shown = " ".join(changed[:EXPLAIN_FILES]) or "-"
    more = f" (+{len(changed) - EXPLAIN_FILES} more)" if len(changed) > EXPLAIN_FILES else ""
    return f"affected: {len(changed)} changed file(s): {shown}{more}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="any_gate_python", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sel = sub.add_parser("plan", help="the package suites a change reaches")
    sel.add_argument("--repo", default=".", help="the repo (default: cwd)")
    sel.add_argument("--explain", action="store_true", help="also print the changed files to stderr")
    sel.add_argument("--plan", action="store_true", help="print `path<TAB>key` per suite (the input of `any-gate test`)")
    sel.add_argument("--all", action="store_true", help="every suite, whatever changed (the release run)")
    sel.add_argument("--reach", type=int, metavar="N", help="print how many suites each of the last N commits reaches, then exit")
    pk = sub.add_parser("packages", help="the package directories a change reaches (for a step that runs once per package)")
    pk.add_argument("--repo", default=".", help="the repo (default: cwd)")
    pk.add_argument("--all", action="store_true", help="every package, whatever changed")
    run = sub.add_parser("run", help="run pytest paths in stages (the runner `any-gate test` calls)")
    run.add_argument(
        "--workers", default="auto", help="xdist workers for the parallel stage: a number, or auto (sized to the tests and box)"
    )
    run.add_argument("--wall", type=float, default=3600.0, help="seconds a stage may take before its tree is stopped")
    run.add_argument("--idle", type=float, default=600.0, help="seconds a stage may stay silent before its tree is stopped")
    run.add_argument(
        "--nice",
        type=int,
        default=10,
        help="raise the test processes' niceness by this much (default 10; 0 leaves it): a gate yields the box to what the owner waits on",
    )
    run.add_argument("--pytest-args", default="", help="extra arguments for every stage's pytest, as one string")
    run.add_argument("paths", nargs="+", metavar="PATH")
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    repo = Path(args.repo).resolve()
    if args.command == "packages":
        names = sorted(workspace(repo)[0]) if args.all else sorted(affected_packages(repo, changed_files(repo), lambda: _lock(repo)))
        sys.stdout.write("".join(f"{name}\n" for name in names))
        return 0
    if args.reach:
        rows = reach(repo, args.reach)
        for sha, files, suites in rows:
            sys.stdout.write(f"{sha} files={files} suites={suites}\n")
        sizes = sorted(suites for _, _, suites in rows)
        median, top = (sizes[len(sizes) // 2], sizes[-1]) if sizes else (0, 0)
        sys.stdout.write(f"commits={len(rows)} median={median} max={top} of {len(workspace(repo)[0])} packages\n")
        return 0
    changed = [] if args.all else changed_files(repo)  # None: the base is unknown, every suite
    paths = everything(repo) if args.all else affected(repo, changed, lambda: _lock(repo))
    if args.explain:
        sys.stderr.write(explain_line(changed) + "\n")
    if (alarm := wide_alarm(repo, paths)) is not None:
        sys.stderr.write(f"any-gate-python: {alarm}\n")
    lines = [f"{path}\t{key}" for path, key in plan(repo, paths, env=os.environ)] if args.plan else paths
    sys.stdout.write("".join(f"{line}\n" for line in lines))
    return 0
