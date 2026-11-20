"""The load-bearing invariant: the package imports no host app (and not blueprint: the gate does not know this package either)."""

from __future__ import annotations

import ast
from pathlib import Path

import any_knowledge

_FORBIDDEN = {"a2web", "a2kay", "a2kit", "blueprint"}


def test_imports_no_consumer() -> None:
    offenders: list[str] = []
    for py in Path(any_knowledge.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                offenders += [f"{py.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in _FORBIDDEN]
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _FORBIDDEN:
                offenders.append(f"{py.name}: from {node.module}")
    assert offenders == []
