"""`blueprint check`: judge a repository against the blueprint, in one process.

Runs as bare `python3` from a shelf clone, no install:

    PYTHONPATH=<shelf>/packages/blueprint/src python3 -m blueprint check --repo .

Exit codes: 0 every checkpoint passes or does not apply · 1 something fails or is not set up ·
2 nothing fails but something could not be checked (never a pass).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from blueprint import report
from blueprint.runner import run


def main(argv: list[str] | None = None) -> int:
    """The command line."""
    parser = argparse.ArgumentParser(prog="blueprint", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    chk = sub.add_parser("check", help="run every checkpoint that applies to the repo")
    chk.add_argument("--repo", default=".", type=Path, help="the repository to judge (default: cwd)")
    chk.add_argument("--concern", help="only this concern's checkpoints")
    chk.add_argument(
        "--audit",
        action="store_true",
        help="also run the audit-only checkpoints: slow ones, and ones needing this machine's own state (bd's database)",
    )
    form = chk.add_mutually_exclusive_group()
    form.add_argument("--json", action="store_true", help="print JSON")
    form.add_argument("--gate", action="store_true", help="print only what is not passing, one line each (for `make blueprint`)")
    chk.add_argument("--write", action="store_true", help="write docs/blueprint/<concern>.md reports")
    args = parser.parse_args(argv)

    result = run(args.repo, concern=args.concern, audit=args.audit)
    text = report.as_json(result) if args.json else report.gate(result) if args.gate else report.markdown(result)
    sys.stdout.write(text + "\n")
    if args.write:
        for path in report.write(result, args.repo.resolve(), date.today()):  # noqa: DTZ011 -- a report date, the owner's calendar
            sys.stderr.write(f"wrote {path}\n")
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
