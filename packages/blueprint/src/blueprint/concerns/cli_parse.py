"""A Python CLI rejects flags it does not know.

`parse_known_args` and `add_help=False` swallow what the parser does not define, `--help` included, so a probe runs the
command: a2kay 2026-10, `serve --help` started a server that committed to main, and five sibling commands had the same
shape (`bridge --help` would have started a relay). Strict parsing then caught `serve` dropping the global `--instance`.
ruff's banned-api cannot see a method on an instance, so this row reads the source. A deliberate two-stage pre-parser
(globals first, then a strict `parse_args` of the rest) says so with `# lenient: <reason>` on its line or earlier in
its function, which the waiver then covers.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

from blueprint.model import Sub, check_each, failing, is_skipped, not_applicable, not_checked, passing, toml_table

if TYPE_CHECKING:
    from blueprint.model import Context, Finding, Profile

_ID = "stack.python-uv.cli-parse"
_STATEMENT = "a CLI rejects flags it does not know: parse_args, not parse_known_args, and --help kept"
_HELP_ID = "stack.python-uv.cli-help-tested"
_HELP_STATEMENT = "every console script has a test that runs it with --help (ADR 0025)"
_WAIVER = re.compile(r"#\s*lenient:\s*\S")
_DEF = re.compile(r"\s*(async\s+)?def\s")
_TESTS = re.compile(r"(^|/)(tests?/|test_[^/]*\.py$|[^/]*_test\.py$|conftest\.py$)")


def _uses_python_uv(profile: Profile) -> bool:
    return "python-uv" in profile.stacks


def _lenient(ctx: Context) -> list[str] | None:
    listed = ctx.git("ls-files", "-z", "*.py")
    if listed is None:
        return None
    hits = []
    for rel in sorted(filter(None, listed.split("\0"))):
        if _TESTS.search(rel) or is_skipped(rel, ctx.profile.ignore):
            continue
        text = ctx.read(rel) or ""
        lines = text.splitlines()
        hits += [f"{rel}:{n}" for n in _lenient_lines(text) if not _waived(lines, n)]
    return hits


def _lenient_lines(text: str) -> list[int]:
    """Lines calling `.parse_known_args(...)` or passing `add_help=False`: the code, never a docstring or comment."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr == "parse_known_args":
            found.add(node.lineno)
        found |= {k.lineno for k in node.keywords if k.arg == "add_help" and isinstance(k.value, ast.Constant) and k.value.value is False}
    return sorted(found)


def _waived(lines: list[str], n: int) -> bool:
    """A waiver on the line, or earlier in the same function (back to its `def`)."""
    for line in reversed(lines[:n]):
        if _WAIVER.search(line):
            return True
        if _DEF.match(line):
            return False
    return False


def _finding(ctx: Context) -> Finding:
    hits = _lenient(ctx)
    if hits is None:
        return not_checked("not a git repository")
    if not hits:
        return passing("no parse_known_args or add_help=False outside tests, or each one waived with `# lenient: <reason>`")
    return failing(
        f"lenient parsing swallows unknown flags, --help included: {', '.join(hits)}",
        "use parse_args and keep add_help (ADR 0025: every command answers --help with its usage and changes nothing); "
        "only a two-stage pre-parser, whose rest goes to a parser that keeps --help, carries `# lenient: <reason>` on its "
        "line or earlier in its function",
    )


def _scripts(ctx: Context) -> dict[str, str]:
    """`[project.scripts]` of the root and each uv workspace member: each console script and the module it runs."""
    root = ctx.toml("pyproject.toml")
    members = toml_table(root, "tool", "uv", "workspace").get("members", [])
    dirs = [
        d.relative_to(ctx.repo).as_posix() for m in (members if isinstance(members, list) else []) for d in sorted(ctx.repo.glob(str(m)))
    ]
    manifests = [root, *(ctx.toml(f"{d}/pyproject.toml") for d in dirs)]
    return {name: str(target).split(":", 1)[0] for data in manifests for name, target in toml_table(data, "project", "scripts").items()}


def _help_tested(ctx: Context) -> Finding:
    scripts = _scripts(ctx)
    if not scripts:
        return not_applicable("no [project.scripts] in pyproject.toml")
    listed = ctx.git("ls-files", "-z", "*.py")
    if listed is None:
        return not_checked("not a git repository")
    tests = [t for rel in filter(None, listed.split("\0")) if _TESTS.search(rel) and "--help" in (t := ctx.read(rel) or "")]
    untested = [
        name
        for name, module in scripts.items()
        if not any(re.search(rf"[\"'\s/]{re.escape(name)}[\"'\s]", t) or module in t for t in tests)
    ]
    if untested:
        return failing(
            f"no test runs {', '.join(untested)} with --help",
            "add a scenario per console script: `<script> --help` exits 0, prints its usage and changes nothing "
            "(no server started, no file written); an unknown flag exits 2 (ADR 0025)",
        )
    return passing(f"{len(scripts)} console script(s), each run with --help by a test")


@check_each(_ID, _STATEMENT, applies=_uses_python_uv, layer="stack")
def cli_parse(ctx: Context) -> list[Sub]:
    """Two rows under the python-uv stack: lenient parsing, and a --help test per console script."""
    return [
        Sub("stack/python-uv", _ID, _STATEMENT, _finding(ctx)),
        Sub("stack/python-uv", _HELP_ID, _HELP_STATEMENT, _help_tested(ctx)),
    ]
