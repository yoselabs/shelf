"""blueprint: the shelf's standard for a software repo, as one installed tool.

  blueprint init    set a repo up: detect its stack, audit, plan, write only what is missing (no shelf clone needed)
  blueprint check   judge the repo against every checkpoint that applies, and say what to fix
  blueprint gate    the steps of `just check` (guard, preset, render, test): the justfile and the git hooks
                    call them; you rarely type one

Installed as a dev dependency (`uv run blueprint check --repo .`), or from a shelf clone with no install:

    PYTHONPATH=<shelf>/packages/blueprint/src python3 -m blueprint check --repo .

Exit codes of `check`: 0 every checkpoint passes or does not apply · 1 something fails or is not set up ·
2 nothing fails but something could not be checked (never a pass).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from blueprint import checkpoints, gate_py, gate_test, guard, init, preset, render, report
from blueprint.runner import run, run_audit

_GATE_HELP = """\
The steps of `just check`. The justfile and the git hooks run them; each one is also a recipe (`just guard`, `just preset`, ...).

  blueprint  guard, preset, the render check and every checkpoint, in one process (`just blueprint`): the gate's one step for them
  guard      refuse a local shelf path in [tool.uv.sources] (the commit hook, and `just guard`)
  preset     compare the repo's ruff and pyrefly config with the shelf's preset, or with the differences it declares (`just preset`)
  render     write the justfile parts blueprint owns (.blueprint/*.just); with --check, fail on any difference (`just render`)
  test       run the tests the change reaches, through any-gate (`just test`)
  lint (ruff and codespell), format, spell, test-all   the python stack's steps; a repo's paths and extra steps are data
                                                       in `[tool.blueprint.gate]`
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="blueprint", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True, metavar="{init,check,gate}")
    ini = sub.add_parser("init", help="set the repo up: detect, audit, plan, write only what is missing; ends with what it could not")
    ini.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    ini.add_argument("--beads", action="store_true", help="also set up beads (`bd init --skip-hooks`); init only suggests it otherwise")
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
        help="the steps of `just check` (guard, preset, render, test): for the justfile and hooks",
        description=_GATE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    steps = gate.add_subparsers(dest="step", required=True, metavar="STEP")
    grd = steps.add_parser("guard", help="refuse a local shelf source in [tool.uv.sources] (the commit hook and `just guard`)")
    grd.add_argument("--committed", action="store_true", help="check HEAD (the gate's question); the default checks the index (the hook's)")
    pre = steps.add_parser("preset", help="compare the repo's linter config with the shelf's preset (`just preset`)")
    pre.add_argument("--repo", default=".", type=Path, help="the repository to check (default: cwd)")
    pre.add_argument("--reference", type=Path, help="compare with this snapshot instead of the packaged one")
    rnd = steps.add_parser("render", help="write the justfile parts the blueprint owns (.blueprint/*.just), or with --check fail on drift")
    rnd.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    rnd.add_argument("--check", action="store_true", help="change nothing; exit 1 when the committed parts differ from what is rendered")
    bpt = steps.add_parser("blueprint", help="guard, preset, the render check and the checkpoints in one process (`just blueprint`)")
    bpt.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    tst = steps.add_parser("test", help="run the tests the change reaches, through any-gate (`just test`)")
    tst.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    tst.add_argument("--receipts", type=Path, help="any-gate's receipts file (default: gate-receipts.json in the git directory)")
    tst.add_argument("--lease-root", type=Path, help="the test-slot lease folder (default: any-gate's)")
    tst.add_argument(
        "--pytest-args",
        default=None,
        help=f"extra arguments for every pytest stage, as one string (default `{gate_test.DEFAULT_PYTEST_ARGS}`; none with coverage)",
    )
    for name, text in (("lint", "ruff check and format --check"), ("spell", "codespell")):
        sp = steps.add_parser(name, help=f"{text} over `[tool.blueprint.gate]` paths (`just {name}`)")
        sp.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
        sp.add_argument("--changed", action="store_true", help="only the files changed against the base (the per-commit gate)")
    fmt = steps.add_parser("format", help="ruff format over `[tool.blueprint.gate]` lint-paths (`just format`)")
    fmt.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    ta = steps.add_parser("test-all", help="every test with the coverage floor, queued behind any-lease (`just test-all`)")
    ta.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    return parser


def known_flags(argv: list[str]) -> tuple[str, set[str]]:
    """`(command path, flags that command accepts)` for the words of a `blueprint` call (`check --brief`, `gate test --repo .`)."""
    parser = _parser()
    path: list[str] = []
    for word in argv:
        subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]  # noqa: SLF001 -- argparse lists no public subparsers
        if word.startswith("-") or not subs or word not in subs[0].choices:
            break
        parser = subs[0].choices[word]
        path.append(word)
    return " ".join(path), {flag for action in parser._actions for flag in action.option_strings}  # noqa: SLF001


def main(argv: list[str] | None = None) -> int:
    """The command line."""
    args = _parser().parse_args(argv)
    if args.command == "init":
        return init.run(args.repo, hooks=not args.no_hooks, beads=args.beads, env=os.environ)
    if args.command == "gate":
        return _GATE_STEPS[args.step](args)
    if args.list is not None:
        return _list(args)
    result = (run_audit if args.audit else run)(args.repo, concern=args.concern)
    text = report.as_json(result) if args.json else report.gate(result) if args.brief else report.markdown(result)
    sys.stdout.write(text + "\n")
    if args.write:
        write = report.write_concern if args.concern else report.write
        for path in write(result, args.repo.resolve(), date.today()):  # noqa: DTZ011 -- a report date, the owner's calendar
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


def _blueprint(args: argparse.Namespace) -> int:
    repo = args.repo.expanduser().resolve()
    codes = [guard.check(committed=True), preset.check(repo), render.check(repo)]
    result = run(repo)
    sys.stdout.write(report.gate(result) + "\n")
    return max(*codes, result.exit_code)


def _test(args: argparse.Namespace) -> int:
    return gate_test.run(
        args.repo.expanduser().resolve(),
        receipts=args.receipts,
        lease_root=args.lease_root,
        pytest_args=args.pytest_args,
        env=dict(os.environ),
    )


def _lint(args: argparse.Namespace) -> int:
    repo = args.repo.expanduser().resolve()
    return gate_py.lint_changed(repo) if args.changed else gate_py.lint(repo)


def _spell(args: argparse.Namespace) -> int:
    repo = args.repo.expanduser().resolve()
    return gate_py.spell_changed(repo) if args.changed else gate_py.spell(repo)


def _format(args: argparse.Namespace) -> int:
    return gate_py.format_(args.repo.expanduser().resolve())


def _test_all(args: argparse.Namespace) -> int:
    return gate_py.test_all(args.repo.expanduser().resolve(), dict(os.environ))


_GATE_STEPS = {
    "blueprint": _blueprint,
    "guard": _guard,
    "preset": _preset,
    "render": _render,
    "test": _test,
    "lint": _lint,
    "spell": _spell,
    "format": _format,
    "test-all": _test_all,
}


if __name__ == "__main__":
    sys.exit(main())
