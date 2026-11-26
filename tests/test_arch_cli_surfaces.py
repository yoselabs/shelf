"""``argparse`` has one home: verb-cli (constitution Article III, bead shelf-tyld.15).

Checked statically over every ``packages/*/src`` and ``tools`` file (tests and ``bench`` excluded). ``import argparse`` is
allowed in verb-cli (the owner), argparse-mcp (it reads a parser it is handed) and any ``__main__.py`` (a module's own
entry point); anything else is a CLI to build on verb-cli. The rows below hold today's other users, each with its reason;
a new file never joins them, and a listed file that no longer imports argparse fails the test (shrink the list).
"""

from __future__ import annotations

import ast
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

import pytest
from any_arch import Row, Rule, check, plant, rows

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_OWNERS = ("packages/verb-cli/", "packages/argparse-mcp/")
_RECIPE = "a standalone script a repo copies alone into its tools/: it cannot import verb-cli"
_ALLOWED = {
    **rows(
        _RECIPE,
        *(
            f"packages/blueprint/src/blueprint/recipes/{name}.py"
            for name in ("check_coverage", "check_dockerfile_pins", "check_godot", "unity_integrity")
        ),
    ),
    **{
        key: Row(reason)
        for key, reason in {
            "packages/blueprint/src/blueprint/secret_scan.py": "blueprint is stdlib only (bare clone, PYTHONPATH): no verb-cli",
            "packages/blueprint/src/blueprint/unit_runner.py": "the runner any-gate spawns: blueprint is stdlib only, no verb-cli",
            "packages/stream-proc/src/stream_proc/_exec_gate.py": "a child-side gate script run by path: stdlib only, no shelf import",
            "tools/api_surface.py": "a repo tool script, run by `uv run python`: stdlib only, no workspace import",
            "tools/catalog.py": "a repo tool script, run by `just`: stdlib only, no workspace import",
            "tools/preset_refresh.py": "a repo tool script, run by `just`: takes no arguments, argparse only serves --help",
            "tools/stdlib_shadow.py": "a repo tool script, run by `just` as bare `python3 -I`: stdlib only, no workspace import",
            "tools/dep_audit.py": "a repo tool script, run by the gate as bare `python3 -I`: stdlib only, no workspace import",
            "tools/corpus_diff.py": "a repo tool script, run by hand before a release: stdlib only, no workspace import",
            "tools/tag_check.py": "a repo tool script, run by the pre-push hook as bare `python3 -I`: stdlib only, no workspace import",
            "packages/any-gate/src/any_gate/cli.py": (
                "needs argparse.REMAINDER (`-- RUNNER`, `-- CMD`) and repeatable flags; verb-cli has neither"
            ),
            "packages/any-knowledge/src/any_knowledge/cli.py": "repeatable flags (--stack, --framework); verb-cli has none",
            "packages/any-gate-python/src/any_gate_python/cli.py": (
                "the runner `any-gate test` calls, beside any-gate's CLI; same flag shapes"
            ),
        }.items()
    },
}


def _imports_argparse(source: Source) -> Iterator[Hit]:
    if source.rel.startswith(_OWNERS) or PurePosixPath(source.rel).name == "__main__.py":
        return
    for node in ast.walk(source.tree):
        if (isinstance(node, ast.Import) and any(a.name == "argparse" for a in node.names)) or (
            isinstance(node, ast.ImportFrom) and node.module == "argparse"
        ):
            yield source.rel, node.lineno


ARGPARSE = Rule(
    "argparse-home",
    "build the CLI on verb-cli, or list the file with a reason",
    _imports_argparse,
    _ALLOWED,
    scope=("packages/*/src/**/*.py", "tools/**/*.py"),
)


def test_argparse_is_imported_only_where_listed_and_every_listed_file_still_imports_it() -> None:
    check(ARGPARSE, _ROOT)


@pytest.mark.parametrize(
    ("source", "path", "expected"),
    [
        ("import argparse", "packages/pkg/src/pkg/mod.py", True),
        ("from argparse import REMAINDER", "packages/pkg/src/pkg/mod.py", True),
        ("import os", "packages/pkg/src/pkg/mod.py", False),
        ("import argparse", "packages/verb-cli/src/verb_cli/mod.py", False),
        ("import argparse", "packages/pkg/src/pkg/__main__.py", False),
    ],
)
def test_the_scanner_sees_what_it_claims_to(tmp_path: Path, source: str, path: str, expected: bool) -> None:
    assert bool(plant(ARGPARSE, tmp_path, source, path)) is expected
