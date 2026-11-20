"""``argparse`` has one home: verb-cli (constitution Article III, bead shelf-tyld.15).

Checked statically over every ``packages/*/src`` and ``tools`` file (tests and ``bench`` excluded). ``import argparse`` is
allowed in verb-cli (the owner), argparse-mcp (it reads a parser it is handed) and any ``__main__.py`` (a module's own
entry point); anything else is a CLI to build on verb-cli. The list below holds today's other users, each with its reason;
a new file never joins it, and a listed file that no longer imports argparse fails the test (shrink the list).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_OWNERS = ("packages/verb-cli/", "packages/argparse-mcp/")
_RECIPE = "a standalone script a repo copies alone into its tools/: it cannot import verb-cli"
_ALLOWED = {
    **{
        f"packages/blueprint/src/blueprint/recipes/{name}.py": _RECIPE
        for name in ("check_coverage", "check_dockerfile_pins", "check_godot", "unity_integrity")
    },
    "packages/blueprint/src/blueprint/secret_scan.py": "blueprint is stdlib only (bare clone, PYTHONPATH): no verb-cli",
    "packages/stream-proc/src/stream_proc/_exec_gate.py": "a child-side gate script run by path: stdlib only, no shelf import",
    "tools/catalog.py": "a repo tool script, run by `just`: stdlib only, no workspace import",
    "tools/preset_refresh.py": "a repo tool script, run by `just`: takes no arguments, argparse only serves --help",
    "tools/tag_check.py": "a repo tool script, run by the pre-push hook as bare `python3 -I`: stdlib only, no workspace import",
    "packages/any-gate/src/any_gate/cli.py": "needs argparse.REMAINDER (`-- RUNNER`, `-- CMD`) and repeatable flags; verb-cli has neither",
    "packages/any-gate-python/src/any_gate_python/cli.py": "the runner `any-gate test` calls, beside any-gate's CLI; same flag shapes",
}


def _sources() -> list[Path]:
    return sorted([*_ROOT.glob("packages/*/src/**/*.py"), *_ROOT.glob("tools/**/*.py")])


def _imports_argparse(tree: ast.AST) -> bool:
    return any(
        (isinstance(n, ast.Import) and any(a.name == "argparse" for a in n.names))
        or (isinstance(n, ast.ImportFrom) and n.module == "argparse")
        for n in ast.walk(tree)
    )


def _users() -> set[str]:
    found: set[str] = set()
    for path in _sources():
        rel = path.relative_to(_ROOT).as_posix()
        if rel.startswith(_OWNERS) or path.name == "__main__.py":
            continue
        if _imports_argparse(ast.parse(path.read_text(encoding="utf-8"))):
            found.add(rel)
    return found


def test_argparse_is_imported_only_where_listed() -> None:
    new = sorted(_users() - _ALLOWED.keys())
    assert not new, f"build the CLI on verb-cli, or list the file with a reason: {new}"


def test_every_listed_file_still_imports_argparse() -> None:
    stale = sorted(_ALLOWED.keys() - _users())
    assert not stale, f"these files no longer import argparse: delete them from _ALLOWED: {stale}"


@pytest.mark.parametrize(
    ("source", "expected"), [("import argparse", True), ("from argparse import REMAINDER", True), ("import os", False)]
)
def test_the_scanner_sees_what_it_claims_to(source: str, expected: bool) -> None:
    assert _imports_argparse(ast.parse(source)) is expected
