"""Boundary guard: any-browser must not import a host framework (kept reusable)."""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "any_browser"


def test_any_browser_imports_no_host() -> None:
    forbidden = {"a2web", "a2kay", "a2kit", "a2effect"}
    offenders: list[str] = []
    for py in _SRC.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [f"{py.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in forbidden]
            elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in forbidden:
                offenders.append(f"{py.name}: from {node.module}")
    assert not offenders, f"any-browser must stay host-agnostic; found: {offenders}"
