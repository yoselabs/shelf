"""The load-bearing invariant: the package imports no host app.

If this fails, a consumer's types or policy tables leaked into the mechanism —
the funnel has stopped being reusable. Keep it green.
"""

from __future__ import annotations

import ast
from pathlib import Path

import llm_wobble

_CONSUMERS = {"a2web", "a2kay"}


def test_imports_no_consumer() -> None:
    pkg_dir = Path(llm_wobble.__file__).parent
    offenders: list[str] = []
    for py in pkg_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [f"{py.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in _CONSUMERS]
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _CONSUMERS:
                offenders.append(f"{py.name}: from {node.module}")
    assert offenders == [], f"llm_wobble must not import a consumer: {offenders}"
