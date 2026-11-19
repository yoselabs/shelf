"""The client imports only the stdlib, child-env (the shelf's binary lookup) and itself, and no consumer app."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import beads_client

_ALLOWED = {"beads_client", "child_env"}
_CONSUMERS = {"a2kay", "a2web", "a2kit", "a2db", "a2atlassian", "lifesim", "taskloop", "delegate"}


def test_imports_only_stdlib_child_env_and_itself() -> None:
    offenders: list[str] = []
    for source in Path(beads_client.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            else:
                continue
            offenders += [
                n
                for n in names
                if n.split(".")[0] in _CONSUMERS or (n.split(".")[0] not in sys.stdlib_module_names and n.split(".")[0] not in _ALLOWED)
            ]
    assert offenders == []
