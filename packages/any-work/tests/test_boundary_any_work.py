"""The work table can be imported without depending on a consumer app."""

from __future__ import annotations

import ast
from pathlib import Path

import any_work

_CONSUMERS = {"a2kay", "a2web", "a2kit", "a2db", "a2atlassian", "lifesim", "taskloop", "any_pipeline"}


def test_imports_no_consumer_and_not_any_pipeline() -> None:
    offenders: list[str] = []
    for source in Path(any_work.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                offenders.extend(alias.name for alias in node.names if alias.name.split(".")[0] in _CONSUMERS)
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _CONSUMERS:
                offenders.append(node.module)
    assert offenders == []
