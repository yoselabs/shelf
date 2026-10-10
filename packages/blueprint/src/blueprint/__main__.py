"""`blueprint check`: judge a repository against the blueprint, in one process.
`blueprint survey`: write the run survey template, or check a filled one.

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

from blueprint import report, survey, templates
from blueprint.profile import detect, load_state
from blueprint.runner import run

RECIPES = Path(__file__).resolve().parent / "recipes"
RECIPE_FILES = {"hooks": "pre-commit-config.yaml"}


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
    form.add_argument("--summary", action="store_true", help="print one row per concern, grouped by layer")
    chk.add_argument("--write", action="store_true", help="write docs/blueprint/<concern>.md reports")
    srv = sub.add_parser("survey", help="write the run survey template, or check a filled one")
    srv.add_argument("--repo", default=".", type=Path, help="the repository the survey is about (default: cwd)")
    srv.add_argument("--check", type=Path, metavar="FILE", help="exit 1 unless FILE answers every question in the closed set")
    tpl = sub.add_parser("template", help="copy missing docs/agents/ files and write the AGENTS.md managed block")
    tpl.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    rcp = sub.add_parser("recipe", help="print a blueprint recipe file")
    rcp.add_argument("name", choices=sorted(RECIPE_FILES), help="hooks: the .pre-commit-config.yaml prek reads")
    args = parser.parse_args(argv)

    if args.command == "template":
        for changed in _install_templates(args.repo):
            sys.stdout.write(f"wrote {changed}\n")
        return 0
    if args.command == "recipe":
        sys.stdout.write((RECIPES / RECIPE_FILES[args.name]).read_text())
        return 0
    if args.command == "survey":
        return _survey(args.repo, args.check)
    result = run(args.repo, concern=args.concern, audit=args.audit)
    if args.json:
        text = report.as_json(result)
    elif args.gate:
        text = report.gate(result)
    elif args.summary:
        text = report.summary(result)
    else:
        text = report.markdown(result)
    sys.stdout.write(text + "\n")
    if args.write:
        for path in report.write(result, args.repo.resolve(), date.today()):  # noqa: DTZ011 -- a report date, the owner's calendar
            sys.stderr.write(f"wrote {path}\n")
    return result.exit_code


def _install_templates(repo: Path) -> list[str]:
    repo = repo.resolve()
    return templates.install(repo, detect(repo, load_state(repo)))


def _survey(repo: Path, filled: Path | None) -> int:
    if filled is None:
        result = run(repo)
        sys.stdout.write(survey.template(repo.resolve().name, result.set_hash) + "\n")
        return 0
    found = survey.problems(filled.read_text())
    for line in found:
        sys.stdout.write(f"survey: {line}\n")
    sys.stdout.write(f"survey: {'incomplete' if found else 'complete'}\n")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
