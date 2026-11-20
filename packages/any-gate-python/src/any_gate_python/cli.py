"""`python -m any_gate_python`: `plan` names the package suites a change reaches; `run` is the pytest runner `any-gate test` calls.

`plan [--plan] [--explain] [--reach N]` prints the pytest paths the change reaches, or with `--plan` one `path<TAB>key` per suite.

`run [--workers auto|N] [--wall S] [--idle S] [--pytest-args "ARGS"] PATH...` runs the paths in pytest stages (parallel, serial,
quarantine); exit 0 when none failed (a failing quarantined test is reported, not blocking), 1 otherwise.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

from any_gate_python.graph import lock_touched, workspace
from any_gate_python.select import affected, changed_files, merge_base, plan, reach
from any_gate_python.stages import run_tests


def _run(args: argparse.Namespace) -> int:
    def show(line: str) -> None:
        sys.stdout.write(line)
        sys.stdout.flush()

    workers = None if args.workers == "auto" else int(args.workers)
    outcome = run_tests(
        args.paths, cwd=Path.cwd(), workers=workers, wall=args.wall, idle=args.idle, on_output=show, extra=shlex.split(args.pytest_args)
    )
    for stage in outcome.stages:
        if stage.stopped:
            sys.stderr.write(f"any-gate-python: {stage.name} stage stopped by the {stage.stopped} limit\n")
    if outcome.quarantined_failed:
        sys.stderr.write("any-gate-python: a quarantined test failed: reported, not blocking\n")
    return 0 if outcome.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="any_gate_python", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sel = sub.add_parser("plan", help="the package suites a change reaches")
    sel.add_argument("--repo", default=".", help="the repo (default: cwd)")
    sel.add_argument("--explain", action="store_true", help="also print the changed files to stderr")
    sel.add_argument("--plan", action="store_true", help="print `path<TAB>key` per suite (the input of `any-gate test`)")
    sel.add_argument("--reach", type=int, metavar="N", help="print how many suites each of the last N commits reaches, then exit")
    run = sub.add_parser("run", help="run pytest paths in stages (the runner `any-gate test` calls)")
    run.add_argument(
        "--workers", default="auto", help="xdist workers for the parallel stage: a number, or auto (sized to the tests and box)"
    )
    run.add_argument("--wall", type=float, default=3600.0, help="seconds a stage may take before its tree is stopped")
    run.add_argument("--idle", type=float, default=600.0, help="seconds a stage may stay silent before its tree is stopped")
    run.add_argument("--pytest-args", default="", help="extra arguments for every stage's pytest, as one string")
    run.add_argument("paths", nargs="+", metavar="PATH")
    args = parser.parse_args(argv)
    if args.command == "run":
        return _run(args)
    repo = Path(args.repo).resolve()
    if args.reach:
        rows = reach(repo, args.reach)
        for sha, files, suites in rows:
            sys.stdout.write(f"{sha} files={files} suites={suites}\n")
        sizes = sorted(suites for _, _, suites in rows)
        median, top = (sizes[len(sizes) // 2], sizes[-1]) if sizes else (0, 0)
        sys.stdout.write(f"commits={len(rows)} median={median} max={top} of {len(workspace(repo)[0])} packages\n")
        return 0
    changed = changed_files(repo)
    paths = affected(repo, changed, lambda: lock_touched(repo, merge_base(repo)))
    if args.explain:
        sys.stderr.write(f"affected: {len(changed)} changed file(s): {' '.join(changed) or '-'}\n")
    lines = [f"{path}\t{key}" for path, key in plan(repo, paths)] if args.plan else paths
    sys.stdout.write("".join(f"{line}\n" for line in lines))
    return 0
