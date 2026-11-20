"""Every console script and directly run script has a test that runs it with --help (ADR 0025).

The old lenient-parsing row (`parse_known_args`, `add_help=False`) was cut 2026-11-20: the one consumer that met it overrode it twice,
and ruff or the help test already catch a command that runs on `--help`.
"""

from __future__ import annotations

import ast
import re
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from blueprint.model import Sub, check_each, failing, is_skipped, not_applicable, passing, toml_table

if TYPE_CHECKING:
    from blueprint.model import Context, Finding, Profile

_HELP_ID = "stack.python-uv.cli-help-tested"
_HELP_STATEMENT = "every console script and directly run script has a test that runs it with --help (ADR 0025)"
_TESTS = re.compile(r"(^|/)(tests?/|test_[^/]*\.py$|[^/]*_test\.py$|conftest\.py$)")


def _uses_python_uv(profile: Profile) -> bool:
    """The python-uv stack is detected."""
    return "python-uv" in profile.stacks


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
        return ctx.not_a_repository() if scripts else not_applicable("no [project.scripts] in pyproject.toml")
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
            f"no test runs {', '.join(untested)} with --help (only tracked test files are read: `git add` a new one)",
            "add a scenario per console script and per directly run script: `<script> --help` exits 0, prints its usage "
            "and changes nothing (no server started, no file written); an unknown flag exits 2 (ADR 0025)",
        )
    return passing(f"{len(scripts)} console script(s) and {len(direct)} directly run script(s), each run with --help by a test")


@check_each(_HELP_ID, _HELP_STATEMENT, applies=_uses_python_uv, layer="stack")
def cli_parse(ctx: Context) -> list[Sub]:
    """One row under the python-uv stack: a --help test per command."""
    return [Sub("stack/python-uv", _HELP_ID, _HELP_STATEMENT, _help_tested(ctx))]
