"""The load-bearing invariant: the package imports no host app.

If this fails, the package has stopped being reusable — a consumer's types or
policy leaked into the mechanism. Keep it green.
"""

from __future__ import annotations

import ast
from pathlib import Path

import http_fetch

_CONSUMERS = {"a2web", "a2kay"}


def test_imports_no_consumer() -> None:
    pkg_dir = Path(http_fetch.__file__).parent
    offenders: list[str] = []
    for py in pkg_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [f"{py.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in _CONSUMERS]
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _CONSUMERS:
                offenders.append(f"{py.name}: from {node.module}")
    assert offenders == [], f"http_fetch must not import a consumer: {offenders}"
