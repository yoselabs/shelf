#!/usr/bin/env python3
"""Run the shelf's onboarding operations against a consumer repo.

This script carries NO judgment of its own — it is the mechanism half of
onboard-consumer-skill's split (design.md D1). Every decision (beads
yes/no, whether this is a python+uv target) is either passed in as a flag
or auto-detected from a fact already on disk (`pyproject.toml` present or
not). The actual ordering and verification guarantees live in
tools/onboard/operations.py's `run_all`, not here.

Usage:
    python3 onboard.py --repo /path/to/consumer [--no-beads] [--shelf-home /path/to/shelf]

Exit code is 0 only if every selected operation's Result.satisfied is True.
Prints one line per operation: `<name>: <outcome> (verified=<bool>) — <message>`.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _resolve_shelf_home(explicit: str | None) -> Path | None:
    """$SHELF_HOME -> ../shelf -> ~/Workspaces/shelf.

    Same fallback chain as docs/consuming-the-shelf.md and
    tools/hooks/install.py's HOOK template.
    """
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("SHELF_HOME"):
        candidates.append(Path(os.environ["SHELF_HOME"]))
    candidates.append(Path(__file__).resolve().parent.parent.parent.parent.parent)  # this skill's own shelf clone
    candidates.append(Path.home() / "Workspaces" / "shelf")
    for candidate in candidates:
        if (candidate / "tools" / "onboard" / "operations.py").is_file():
            return candidate
    return None


def _run(shelf_home: Path, repo: Path, *, want_beads: bool) -> int:
    # GuardOperation shells out to tools/hooks/install.py, which resolves the shelf clone
    # itself via $SHELF_HOME -- propagate what THIS script resolved so the two never disagree
    # (an unset SHELF_HOME here previously let that subprocess fall back to a different, often
    # wrong, shelf clone than the one this script is actually importing operations from).
    os.environ["SHELF_HOME"] = str(shelf_home)
    sys.path.insert(0, str(shelf_home / "tools"))
    # Deferred: sys.path must carry the shelf clone before these resolve.
    from onboard.beads import BeadsOperation  # noqa: PLC0415
    from onboard.guard import GuardOperation  # noqa: PLC0415
    from onboard.linter_preset import LinterPresetOperation  # noqa: PLC0415
    from onboard.operations import Operation, run_all  # noqa: PLC0415
    from onboard.resolver_block import ResolverBlockOperation  # noqa: PLC0415
    from onboard.verify import all_satisfied  # noqa: PLC0415

    ops: list[Operation] = [GuardOperation(repo), ResolverBlockOperation(repo)]
    if want_beads:
        ops.append(BeadsOperation(repo))
    if (repo / "pyproject.toml").exists():
        ops.append(LinterPresetOperation(repo))
    else:
        print("linter-preset: skipped — no pyproject.toml found, this is not a python+uv target")

    results = run_all(ops)
    for name, result in results.items():
        print(f"{name}: {result.outcome.value} (verified={result.verified}) — {result.message}")

    return 0 if all_satisfied(results) else 1


def main() -> int:
    """Parse args, resolve the shelf clone, and run the selected operations against `--repo`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="path to the consumer repo being onboarded")
    parser.add_argument("--no-beads", action="store_true", help="skip the beads operation (default: beads is applied)")
    parser.add_argument("--shelf-home", default=None, help="override shelf clone location")
    args = parser.parse_args()

    shelf_home = _resolve_shelf_home(args.shelf_home)
    if shelf_home is None:
        print("could not find a shelf clone (checked --shelf-home, $SHELF_HOME, ../shelf, ~/Workspaces/shelf)", file=sys.stderr)
        print("clone one: git clone https://github.com/yoselabs/shelf ~/Workspaces/shelf", file=sys.stderr)
        return 2

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"not a directory: {repo}", file=sys.stderr)
        return 2

    if repo == shelf_home.resolve():
        print(f"refusing to onboard {repo} onto itself — it IS the shelf, not a consumer of it", file=sys.stderr)
        print("(the resolver block would otherwise be projected into the shelf's own AGENTS.md)", file=sys.stderr)
        return 2

    return _run(shelf_home, repo, want_beads=not args.no_beads)


if __name__ == "__main__":
    raise SystemExit(main())
