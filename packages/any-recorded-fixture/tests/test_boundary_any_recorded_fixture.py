"""The recorded fixture can be imported without depending on a consumer app."""

from __future__ import annotations

import ast
from pathlib import Path

import any_recorded_fixture

_CONSUMERS = {"a2kay", "a2web", "a2kit", "a2db", "a2atlassian", "lifesim", "taskloop"}


def test_imports_no_consumer() -> None:
    offenders: list[str] = []
    for source in Path(any_recorded_fixture.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                offenders.extend(alias.name for alias in node.names if alias.name.split(".")[0] in _CONSUMERS)
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _CONSUMERS:
                offenders.append(node.module)
    assert offenders == []
