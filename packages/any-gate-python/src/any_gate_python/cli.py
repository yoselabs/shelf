"""`python -m any_gate_python`: the package suites the change reaches, as pytest paths or as a plan for `any-gate test`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from any_gate_python.graph import lock_touched, workspace
from any_gate_python.select import affected, changed_files, merge_base, plan, reach


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="any_gate_python", description=__doc__)
    parser.add_argument("--repo", default=".", help="the repo (default: cwd)")
    parser.add_argument("--explain", action="store_true", help="also print the changed files to stderr")
    parser.add_argument("--plan", action="store_true", help="print `path<TAB>key` per suite (the input of `any-gate test`)")
    parser.add_argument("--reach", type=int, metavar="N", help="print how many suites each of the last N commits reaches, then exit")
    args = parser.parse_args(argv)
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
