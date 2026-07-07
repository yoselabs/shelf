"""Boundary guard: anyembed must not import a2kay (kept reusable)."""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "anyembed"


def test_anyembed_imports_no_a2kay() -> None:
    offenders: list[str] = []
    for py in _SRC.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [f"{py.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in {"a2kay", "a2effect", "a2kit"}]
            elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in {"a2kay", "a2effect", "a2kit"}:
                offenders.append(f"{py.name}: from {node.module}")
    assert not offenders, f"anyembed must stay host-agnostic; found: {offenders}"
