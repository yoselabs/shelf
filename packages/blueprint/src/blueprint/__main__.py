"""`blueprint check`: judge a repository against the blueprint, in one process.
`blueprint survey`: write the run survey template, or check a filled one.

Installed as a dev dependency (`uv run blueprint check --repo .`), or from a shelf clone with no install:

    PYTHONPATH=<shelf>/packages/blueprint/src python3 -m blueprint check --repo .

`blueprint guard`, `blueprint preset`, `blueprint render` and `blueprint test` are the gate steps that need no shelf clone.

Exit codes: 0 every checkpoint passes or does not apply · 1 something fails or is not set up ·
2 nothing fails but something could not be checked (never a pass).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from blueprint import adr, checkpoints, gate_test, guard, preset, render, report, survey, templates
from blueprint.profile import detect, load_state
from blueprint.runner import run, run_audit

RECIPES = Path(__file__).resolve().parent / "recipes"
RECIPE_FILES = {
    "hooks": "pre-commit-config.yaml",
    "unity-integrity": "unity_integrity.py",
    "dotnet-coverage": "check_coverage.py",
    "godot-integrity": "check_godot.py",
    "godot-test": "godot-test.just",
    "dockerfile-pins": "check_dockerfile_pins.py",
    "compose-policy": "compose_policy.rego",
}


def _parser() -> argparse.ArgumentParser:
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
    form.add_argument("--gate", action="store_true", help="print only what is not passing, one line each (for `just blueprint`)")
    form.add_argument("--summary", action="store_true", help="print one row per concern, grouped by layer")
    chk.add_argument("--write", action="store_true", help="write docs/blueprint/<concern>.md reports")
    srv = sub.add_parser("survey", help="write the run survey template, or check a filled one")
    srv.add_argument("--repo", default=".", type=Path, help="the repository the survey is about (default: cwd)")
    srv.add_argument("--check", type=Path, metavar="FILE", help="exit 1 unless FILE answers every question in the closed set")
    tpl = sub.add_parser("template", help="copy missing docs/agents/ files and write the AGENTS.md managed block")
    tpl.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    idx = sub.add_parser("adr-index", help="print docs/adr/INDEX.md as the ADRs generate it")
    idx.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    idx.add_argument("--write", action="store_true", help="write it to docs/adr/INDEX.md instead")
    rcp = sub.add_parser("recipe", help="print a blueprint recipe file")
    rcp.add_argument(
        "name",
        choices=sorted(RECIPE_FILES),
        help=(
            "hooks: .pre-commit-config.yaml; godot-test: a justfile recipe; compose-policy: a policy/ rego file; "
            "the others: a tools/ script, named in the profile"
        ),
    )
    cps = sub.add_parser(
        "checkpoints",
        help="list every checkpoint: its id, statement and the fact that turns it on",
        description=(
            "List every checkpoint blueprint can report: the id (what an override or a declared fact names), "
            "the statement, and the fact that turns it on. Profile rows are listed per stack and role."
        ),
    )
    cps.add_argument("prefix", nargs="?", default="", help="only checkpoints whose id starts with this (e.g. stack.dockerfile)")
    cps.add_argument("--json", action="store_true", help="print JSON")
    grd = sub.add_parser("guard", help="refuse a local shelf source in [tool.uv.sources] (the commit hook and `just guard`)")
    grd.add_argument("--committed", action="store_true", help="check HEAD (the gate's question); the default checks the index (the hook's)")
    pre = sub.add_parser("preset", help="compare the repo's linter config with the shelf's preset (`just preset`)")
    pre.add_argument("--repo", default=".", type=Path, help="the repository to check (default: cwd)")
    pre.add_argument("--reference", type=Path, help="compare with this snapshot instead of the packaged one")
    pre.add_argument("--refresh", action="store_true", help="in the shelf: rewrite the packaged snapshot from its own files")
    rnd = sub.add_parser("render", help="write the justfile parts the blueprint owns (.blueprint/*.just), or with --check fail on drift")
    rnd.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    rnd.add_argument("--check", action="store_true", help="change nothing; exit 1 when the committed parts differ from what is rendered")
    tst = sub.add_parser("test", help="run the gate's tests through any-gate with the repo's adapter runner (`just test`)")
    tst.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    tst.add_argument("--receipts", type=Path, help="any-gate's receipts file (default: gate-receipts.json in the git directory)")
    tst.add_argument("--lease-root", type=Path, help="the test-slot lease folder (default: any-gate's)")
    tst.add_argument("--pytest-args", default=gate_test.DEFAULT_PYTEST_ARGS, help="extra arguments for every pytest stage, as one string")
    return parser


def main(argv: list[str] | None = None) -> int:
    """The command line."""
    args = _parser().parse_args(argv)

    if args.command in _GATE_VERBS:
        return _GATE_VERBS[args.command](args)
    if args.command == "survey":
        return _survey(args.repo, args.check)
    commands = {
        "checkpoints": _checkpoints,
        "template": _template,
        "adr-index": _adr_index,
        "recipe": _recipe,
    }
    if args.command in commands:
        return commands[args.command](args)
    result = (run_audit if args.audit else run)(args.repo, concern=args.concern)
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
        write = report.write_concern if args.concern else report.write
        for path in write(result, args.repo.resolve(), date.today()):  # noqa: DTZ011 -- a report date, the owner's calendar
            sys.stderr.write(f"wrote {path}\n")
    return result.exit_code


def _guard(args: argparse.Namespace) -> int:
    return guard.check(committed=args.committed)


def _preset(args: argparse.Namespace) -> int:
    if args.refresh:
        sys.stdout.write(f"wrote {preset.refresh(args.repo.resolve())}\n")
        return 0
    return preset.check(args.repo.expanduser().resolve(), args.reference)


def _render(args: argparse.Namespace) -> int:
    repo = args.repo.expanduser().resolve()
    if args.check:
        return render.check(repo)
    for changed in render.write(repo):
        sys.stdout.write(f"wrote {changed}\n")
    return 0


def _test(args: argparse.Namespace) -> int:
    return gate_test.run(args.repo.expanduser().resolve(), receipts=args.receipts, lease_root=args.lease_root, pytest_args=args.pytest_args)


# The verbs that are gate steps: no shelf clone, no checkpoint run.
_GATE_VERBS = {"guard": _guard, "preset": _preset, "render": _render, "test": _test}


def _checkpoints(args: argparse.Namespace) -> int:
    rows = checkpoints.listing(args.prefix)
    sys.stdout.write((checkpoints.as_json(rows) if args.json else checkpoints.as_table(rows)) + "\n")
    return 0


def _template(args: argparse.Namespace) -> int:
    for changed in _install_templates(args.repo):
        sys.stdout.write(f"wrote {changed}\n")
    return 0


def _adr_index(args: argparse.Namespace) -> int:
    text = adr.index(args.repo.resolve())
    if args.write:
        (args.repo / adr.FOLDER / adr.INDEX).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


def _recipe(args: argparse.Namespace) -> int:
    sys.stdout.write((RECIPES / RECIPE_FILES[args.name]).read_text())
    return 0


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
