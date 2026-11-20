"""The package imports the standard library and, in filestore.py alone, atomic-io: no host app, no third-party code."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import any_pipeline


def test_imports_only_the_standard_library_atomic_io_and_content_digest_for_the_file_store() -> None:
    offenders: list[str] = []
    for source in Path(any_pipeline.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            allowed = (
                sys.stdlib_module_names | {"any_pipeline"} | ({"atomic_io", "content_digest"} if source.name == "filestore.py" else set())
            )
            offenders.extend(n for n in names if n.split(".")[0] not in allowed)
    assert offenders == []
