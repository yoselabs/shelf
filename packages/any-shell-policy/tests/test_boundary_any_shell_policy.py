"""The package can be vendored: stdlib only, and no consumer app is imported."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import any_shell_policy

_CONSUMERS = {"a2kay", "a2web", "a2kit", "a2db", "a2atlassian", "lifesim", "taskloop", "delegate"}


def _imported(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0:
        return [node.module or ""]
    return []


def test_imports_only_stdlib_and_itself() -> None:
    allowed = set(sys.stdlib_module_names) | {"any_shell_policy"}
    offenders: list[str] = []
    for source in Path(any_shell_policy.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            names = _imported(node)
            offenders.extend(n for n in names if n.split(".")[0] not in allowed or n.split(".")[0] in _CONSUMERS)
    assert offenders == []
