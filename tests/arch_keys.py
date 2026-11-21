"""Row keys finer than a file for arch tests: `path:Class.function`, so a file with an outcome and a debt gets two rows."""

from __future__ import annotations

import ast


def qualnames(tree: ast.Module) -> dict[ast.AST, str]:
    """Each node -> the dotted names of the classes and functions around it (`Class.method`), or `<module>`."""
    names: dict[ast.AST, str] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = prefix
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                inner = f"{prefix}.{child.name}" if prefix else child.name
            names[child] = inner or "<module>"
            visit(child, inner)

    visit(tree, "")
    return names
