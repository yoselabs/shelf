"""The package imports only the standard library: no host app, no third-party code."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import any_pipeline


def test_imports_only_the_standard_library() -> None:
    offenders: list[str] = []
    for source in Path(any_pipeline.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            offenders.extend(n for n in names if n.split(".")[0] not in sys.stdlib_module_names | {"any_pipeline"})
    assert offenders == []
