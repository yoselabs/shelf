"""git_porcelain stays host-agnostic: no module imports a host package.

Stricter than the shelf-wide boundary test, which does not forbid a2effect.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "git_porcelain"
_HOSTS = {"a2kay", "a2effect", "a2kit"}


def test_git_porcelain_imports_no_host() -> None:
    offenders: list[str] = []
    for py in _SRC.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [f"{py.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in _HOSTS]
            elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in _HOSTS:
                offenders.append(f"{py.name}: from {node.module}")
    assert not offenders, f"git_porcelain must stay host-agnostic; found: {offenders}"
