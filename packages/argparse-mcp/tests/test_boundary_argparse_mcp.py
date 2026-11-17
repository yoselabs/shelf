"""The package imports no host app."""

from __future__ import annotations

import ast
from pathlib import Path

import argparse_mcp

_CONSUMERS = {"a2web", "a2kay", "a2kit", "ogy"}


def test_imports_no_consumer() -> None:
    offenders: list[str] = []
    for py in Path(argparse_mcp.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                offenders += [f"{py.name}: {a.name}" for a in node.names if a.name.split(".")[0] in _CONSUMERS]
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _CONSUMERS:
                offenders.append(f"{py.name}: {node.module}")
    assert offenders == []
