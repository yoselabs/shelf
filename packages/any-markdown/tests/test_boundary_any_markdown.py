"""The load-bearing invariant: the package imports no host app.

If this fails, the package has stopped being reusable — a consumer's types or
policy leaked into the mechanism. Keep it green.
"""

from __future__ import annotations

import ast
from pathlib import Path

import any_markdown

_CONSUMERS = {"a2web", "a2kay"}


def test_imports_no_consumer() -> None:
    pkg_dir = Path(any_markdown.__file__).parent
    offenders: list[str] = []
    for py in pkg_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [f"{py.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in _CONSUMERS]
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _CONSUMERS:
                offenders.append(f"{py.name}: from {node.module}")
    assert offenders == [], f"any-markdown imports a consumer: {offenders}"


def test_knows_nothing_about_a_consumers_identity_rules() -> None:
    # Resolution 0010, generic-first: resolving an anchor to a target, and any id rule
    # underneath it, is the app's business. This package reports what was written.
    assert not hasattr(any_markdown, "canonical_id")
    assert not any("kay://" in py.read_text(encoding="utf-8") for py in Path(any_markdown.__file__).parent.rglob("*.py"))
