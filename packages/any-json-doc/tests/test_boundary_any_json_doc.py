"""The package can be imported without a consumer app and needs only the standard library plus atomic_io and process_lock."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import any_json_doc

_CONSUMERS = {"a2kay", "a2web", "a2kit", "a2db", "a2atlassian", "lifesim", "taskloop", "delegate"}


def _imports() -> set[str]:
    found: set[str] = set()
    for source in Path(any_json_doc.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                found.add(node.module.split(".")[0])
    return found


def test_imports_no_consumer() -> None:
    assert _imports() & _CONSUMERS == set()


def test_imports_only_the_standard_library_and_declared_dependencies() -> None:
    assert {m for m in _imports() if m not in sys.stdlib_module_names} <= {
        "any_json_doc",
        "atomic_io",
        "process_lock",
    }
