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

from blueprint.model import Sub, check_each, failing, is_skipped, not_checked, passing

if TYPE_CHECKING:
    from blueprint.model import Context, Finding, Profile

_ID = "stack.python-uv.cli-parse"
_STATEMENT = "a CLI rejects flags it does not know: parse_args, not parse_known_args, and --help kept"
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
        "use parse_args and keep add_help; a deliberate two-stage pre-parser (globals first, then a strict parse_args of the "
        "rest) carries `# lenient: <reason>` on its line or earlier in its function; so does a parse_known_args that refuses "
        "every leftover",
    )


@check_each(_ID, _STATEMENT, applies=_uses_python_uv, layer="stack")
def cli_parse(ctx: Context) -> list[Sub]:
    """One row under the python-uv stack."""
    return [Sub("stack/python-uv", _ID, _STATEMENT, _finding(ctx))]
