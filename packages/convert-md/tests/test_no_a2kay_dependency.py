"""The load-bearing invariant: convert_md depends on no host app.

If this ever fails, the package has stopped being reusable — a consumer's types
or policy leaked into the mechanism. Keep it green.
"""

from __future__ import annotations

import ast
from pathlib import Path

import convert_md


def test_convert_md_imports_no_a2kay() -> None:
    pkg_dir = Path(convert_md.__file__).parent
    offenders: list[str] = []
    for py in pkg_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [f"{py.name}: import {a.name}" for a in node.names if a.name.split(".")[0] == "a2kay"]
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "a2kay":
                offenders.append(f"{py.name}: from {node.module}")
    assert offenders == [], f"convert_md must not import a2kay: {offenders}"
