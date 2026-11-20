"""blueprint: the shelf's standard for a software repo, as one installed tool.

  blueprint init    set a repo up: detect its stack, audit, plan, write only what is missing (no shelf clone needed)
  blueprint check   judge the repo against every checkpoint that applies, and say what to fix
  blueprint gate    the steps of `just check` (guard, preset, render, test, adr-index): the justfile and the git hooks
                    call them; you rarely type one

Installed as a dev dependency (`uv run blueprint check --repo .`), or from a shelf clone with no install:

    PYTHONPATH=<shelf>/packages/blueprint/src python3 -m blueprint check --repo .

Exit codes of `check`: 0 every checkpoint passes or does not apply · 1 something fails or is not set up ·
2 nothing fails but something could not be checked (never a pass).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from blueprint import adr, checkpoints, gate_test, guard, init, preset, render, report
from blueprint.runner import run

_GATE_HELP = """\
The steps of `just check`. The justfile and the git hooks run them; each one is also a recipe (`just guard`, `just preset`, ...).

  guard      refuse a local shelf path in [tool.uv.sources] (the commit hook, and `just guard`)
  preset     compare the repo's ruff and pyrefly config with the shelf's preset, or with the differences it declares (`just preset`)
  render     write the justfile parts blueprint owns (.blueprint/*.just); with --check, fail on any difference (`just render`)
  test       run the tests the change reaches, through any-gate (`just test`)
  adr-index  print docs/adr/INDEX.md as the ADRs generate it; with --write, write it
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="blueprint", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True, metavar="{init,check,gate}")
    ini = sub.add_parser("init", help="set the repo up: detect, audit, plan, write only what is missing; ends with what it could not")
    ini.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    ini.add_argument("--no-hooks", action="store_true", help="write no hook config and install no git hooks")
    chk = sub.add_parser("check", help="judge the repo against every checkpoint that applies")
    chk.add_argument("--repo", default=".", type=Path, help="the repository to judge (default: cwd)")
    chk.add_argument("--concern", help="only this concern's checkpoints")
    chk.add_argument(
        "--audit",
        action="store_true",
        help="also run the audit-only checkpoints: slow ones, and ones needing this machine's own state (bd's database)",
    )
    chk.add_argument(
        "--list",
        nargs="?",
        const="",
        metavar="PREFIX",
        help="list the checkpoints instead (id, statement, what turns it on), only ids starting with PREFIX; --json for JSON",
    )
    form = chk.add_mutually_exclusive_group()
    form.add_argument("--json", action="store_true", help="print JSON")
    form.add_argument("--brief", action="store_true", help="print only what is not passing, one line each (what `just blueprint` prints)")
    chk.add_argument("--write", action="store_true", help="write docs/blueprint/<concern>.md reports")
    gate = sub.add_parser(
        "gate",
        help="the steps of `just check` (guard, preset, render, test, adr-index): for the justfile and hooks",
        description=_GATE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    steps = gate.add_subparsers(dest="step", required=True, metavar="STEP")
    idx = steps.add_parser("adr-index", help="print docs/adr/INDEX.md as the ADRs generate it")
    idx.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    idx.add_argument("--write", action="store_true", help="write it to docs/adr/INDEX.md instead")
    grd = steps.add_parser("guard", help="refuse a local shelf source in [tool.uv.sources] (the commit hook and `just guard`)")
    grd.add_argument("--committed", action="store_true", help="check HEAD (the gate's question); the default checks the index (the hook's)")
    pre = steps.add_parser("preset", help="compare the repo's linter config with the shelf's preset (`just preset`)")
    pre.add_argument("--repo", default=".", type=Path, help="the repository to check (default: cwd)")
    pre.add_argument("--reference", type=Path, help="compare with this snapshot instead of the packaged one")
    rnd = steps.add_parser("render", help="write the justfile parts the blueprint owns (.blueprint/*.just), or with --check fail on drift")
    rnd.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    rnd.add_argument("--check", action="store_true", help="change nothing; exit 1 when the committed parts differ from what is rendered")
    tst = steps.add_parser("test", help="run the tests the change reaches, through any-gate (`just test`)")
    tst.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    tst.add_argument("--receipts", type=Path, help="any-gate's receipts file (default: gate-receipts.json in the git directory)")
    tst.add_argument("--lease-root", type=Path, help="the test-slot lease folder (default: any-gate's)")
    tst.add_argument("--pytest-args", default=gate_test.DEFAULT_PYTEST_ARGS, help="extra arguments for every pytest stage, as one string")
    return parser


def main(argv: list[str] | None = None) -> int:
    """The command line."""
    args = _parser().parse_args(argv)
    if args.command == "init":
        return init.run(args.repo, hooks=not args.no_hooks)
    if args.command == "gate":
        return _GATE_STEPS[args.step](args)
    if args.list is not None:
        return _list(args)
    result = run(args.repo, concern=args.concern, audit=args.audit)
    text = report.as_json(result) if args.json else report.gate(result) if args.brief else report.markdown(result)
    sys.stdout.write(text + "\n")
    if args.write:
        for path in report.write(result, args.repo.resolve(), date.today(), prune=args.concern is None):  # noqa: DTZ011 -- a report date, the owner's calendar
            sys.stderr.write(f"wrote {path}\n")
    return result.exit_code


def _list(args: argparse.Namespace) -> int:
    rows = checkpoints.listing(args.list)
    sys.stdout.write((checkpoints.as_json(rows) if args.json else checkpoints.as_table(rows)) + "\n")
    return 0


def _guard(args: argparse.Namespace) -> int:
    return guard.check(committed=args.committed)


def _preset(args: argparse.Namespace) -> int:
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


def _adr_index(args: argparse.Namespace) -> int:
    text = adr.index(args.repo.resolve())
    if args.write:
        (args.repo / adr.FOLDER / adr.INDEX).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


_GATE_STEPS = {"guard": _guard, "preset": _preset, "render": _render, "test": _test, "adr-index": _adr_index}


if __name__ == "__main__":
    sys.exit(main())
