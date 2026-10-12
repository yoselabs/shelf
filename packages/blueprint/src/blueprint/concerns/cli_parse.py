"""A Python CLI rejects flags it does not know.

`parse_known_args` and `add_help=False` swallow what the parser does not define, `--help` included, so a probe runs the
command: a2kay 2026-10, `serve --help` started a server that committed to main, and five sibling commands had the same
shape (`bridge --help` would have started a relay). Strict parsing then caught `serve` dropping the global `--instance`.
ruff's banned-api cannot see a method on an instance, so this row reads the source. A deliberate two-stage pre-parser
(globals first, then a strict `parse_args` of the rest) says so with an `[[override]]` in docs/blueprint/blueprint.toml:
this checkpoint's id, `scope` the file (or `file:line`), a reason. The old `# lenient: <reason>` comment is no longer
honoured; where one is still found the evidence prints the override to write in its place.
"""

from __future__ import annotations

import ast
import re
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from blueprint.model import MOVE, Sub, check_each, failing, is_skipped, not_applicable, not_checked, override_toml, passing, toml_table

if TYPE_CHECKING:
    from blueprint.model import Context, Finding, Profile
    from blueprint.profile import Override

_ID = "stack.python-uv.cli-parse"
_STATEMENT = "a CLI rejects flags it does not know: parse_args, not parse_known_args, and --help kept"
_HELP_ID = "stack.python-uv.cli-help-tested"
_HELP_STATEMENT = "every console script and directly run script has a test that runs it with --help (ADR 0025)"
_MARKER = re.compile(r"#\s*lenient:\s*(\S.*)")
_DEF = re.compile(r"\s*(async\s+)?def\s")
_TESTS = re.compile(r"(^|/)(tests?/|test_[^/]*\.py$|[^/]*_test\.py$|conftest\.py$)")


def _uses_python_uv(profile: Profile) -> bool:
    """The python-uv stack is detected."""
    return "python-uv" in profile.stacks


def _lenient(ctx: Context) -> tuple[list[str], list[tuple[str, Override]], list[str]] | None:
    """The offenders (`path:line`), those a scoped override excuses, and the override text for each old marker found."""
    listed = ctx.git("ls-files", "-z", "*.py")
    if listed is None:
        return None
    hits: list[str] = []
    excused: list[tuple[str, Override]] = []
    moves: list[str] = []
    for rel in sorted(filter(None, listed.split("\0"))):
        if _TESTS.search(rel) or is_skipped(rel, ctx.profile.ignore):
            continue
        text = ctx.read(rel) or ""
        lines = text.splitlines()
        for n in _lenient_lines(text):
            where = f"{rel}:{n}"
            if (override := ctx.excused(_ID, rel, n)) is not None:
                excused.append((where, override))
                continue
            hits.append(where)
            if (reason := _marker_reason(lines, n)) is not None:
                moves.append(override_toml(_ID, where, reason, expires=ctx.expiry_hint()))
    return hits, excused, moves


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


def _marker_reason(lines: list[str], n: int) -> str | None:
    """The reason of an old `# lenient:` comment on line `n` or earlier in the same function (back to its `def`), else None."""
    for line in reversed(lines[:n]):
        if m := _MARKER.search(line):
            return m.group(1).strip()
        if _DEF.match(line):
            return None
    return None


def _finding(ctx: Context) -> Finding:
    found = _lenient(ctx)
    if found is None:
        return not_checked("not a git repository")
    hits, excused, moves = found
    if not hits:
        used = "; ".join(f"{where} by override ({o.reason})" for where, o in excused)
        return passing(
            "no parse_known_args or add_help=False outside tests" + (f", or each one excused by an [[override]]: {used}" if excused else "")
        )
    evidence = f"lenient parsing swallows unknown flags, --help included: {', '.join(hits)}"
    if moves:
        evidence += f"; `# lenient:` is no longer honoured, {MOVE}:\n" + "\n\n".join(moves)
    return failing(
        evidence,
        "use parse_args and keep add_help (ADR 0025: every command answers --help with its usage and changes nothing); "
        "only a two-stage pre-parser, whose rest goes to a parser that keeps --help, is excused: an [[override]] "
        f'id = "{_ID}" with scope = "<file>" (or "<file>:<line>") in docs/blueprint/blueprint.toml',
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


def _is_main_guard(node: ast.stmt) -> bool:
    """A top-level `if __name__ == "__main__":`."""
    if not (isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)):
        return False
    return node.test.left.id == "__name__" and any(isinstance(c, ast.Constant) and c.value == "__main__" for c in node.test.comparators)


def _parses_arguments(tree: ast.Module) -> bool:
    """An `ArgumentParser(...)` call, a `sys.argv` reference, or a click/typer import, anywhere in the module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Attribute) and f.attr == "ArgumentParser") or (isinstance(f, ast.Name) and f.id == "ArgumentParser"):
                return True
        elif (
            (isinstance(node, ast.Attribute) and node.attr == "argv" and isinstance(node.value, ast.Name) and node.value.id == "sys")
            or (isinstance(node, ast.Import) and any(a.name.split(".")[0] in {"click", "typer"} for a in node.names))
            or (isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in {"click", "typer"})
        ):
            return True
    return False


def _direct_scripts(ctx: Context, files: list[str]) -> list[str]:
    """Tracked `.py` files outside tests with a `__main__` block that parses arguments: a command run directly."""
    found = []
    for rel in files:
        if _TESTS.search(rel) or is_skipped(rel, ctx.profile.ignore):
            continue
        try:
            tree = ast.parse(ctx.read(rel) or "")
        except SyntaxError:
            continue
        if any(_is_main_guard(n) for n in tree.body) and _parses_arguments(tree):
            found.append(rel)
    return found


def _help_tested(ctx: Context) -> Finding:
    scripts = _scripts(ctx)
    listed = ctx.git("ls-files", "-z", "*.py")
    if listed is None:
        return not_checked("not a git repository") if scripts else not_applicable("no [project.scripts] in pyproject.toml")
    files = sorted(filter(None, listed.split("\0")))
    direct = _direct_scripts(ctx, files)
    if not scripts and not direct:
        return not_applicable("no [project.scripts] in pyproject.toml and no directly run script that parses arguments")
    tests = [t for rel in files if _TESTS.search(rel) and "--help" in (t := ctx.read(rel) or "")]
    untested = [
        name
        for name, module in scripts.items()
        if not any(re.search(rf"[\"'\s/]{re.escape(name)}[\"'\s]", t) or module in t for t in tests)
    ]
    untested += [rel for rel in direct if not any(rel in t or PurePosixPath(rel).stem in t for t in tests)]
    if untested:
        return failing(
            f"no test runs {', '.join(untested)} with --help",
            "add a scenario per console script and per directly run script: `<script> --help` exits 0, prints its usage "
            "and changes nothing (no server started, no file written); an unknown flag exits 2 (ADR 0025)",
        )
    return passing(f"{len(scripts)} console script(s) and {len(direct)} directly run script(s), each run with --help by a test")


@check_each(_ID, _STATEMENT, applies=_uses_python_uv, layer="stack")
def cli_parse(ctx: Context) -> list[Sub]:
    """Two rows under the python-uv stack: lenient parsing, and a --help test per command."""
    return [
        Sub("stack/python-uv", _ID, _STATEMENT, _finding(ctx)),
        Sub("stack/python-uv", _HELP_ID, _HELP_STATEMENT, _help_tested(ctx)),
    ]
