#!/usr/bin/env python3
"""Python SLOC measurement matching task-loop's gate_rules counter."""

from __future__ import annotations

import ast
import io
import tokenize
import tomllib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path


def child_statements(node: ast.AST) -> Iterator[ast.AST]:
    yield from getattr(node, "body", ())
    for handler in getattr(node, "handlers", ()):
        yield from handler.body
    yield from getattr(node, "orelse", ())
    yield from getattr(node, "finalbody", ())
    for case in getattr(node, "cases", ()):
        yield from case.body


def sloc_lines(text: str, tree: ast.Module) -> set[int]:
    skip = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER}
    lines: set[int] = set()
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type not in skip:
            lines.update(range(tok.start[0], tok.end[0] + 1))
    pending: list[ast.AST] = [tree]
    while pending:
        node = pending.pop()
        pending.extend(child_statements(node))
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                lines.difference_update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return lines


def walk_defs(node: ast.AST, prefix: str = "") -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    for child in child_statements(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield prefix + child.name, child
            yield from walk_defs(child, prefix + child.name + ".")
        elif isinstance(child, ast.ClassDef):
            yield from walk_defs(child, prefix + child.name + ".")
        else:
            yield from walk_defs(child, prefix)


def measure(text: str) -> tuple[int, dict[str, int]]:
    tree = ast.parse(text)
    lines = sloc_lines(text, tree)
    funcs: dict[str, int] = {}
    for qual, node in walk_defs(tree):
        start = min([node.lineno] + [d.lineno for d in node.decorator_list])
        size = len(lines.intersection(range(start, (node.end_lineno or node.lineno) + 1)))
        funcs[qual] = max(size, funcs.get(qual, 0))
    return len(lines), funcs


def load_caps(root: Path) -> dict[str, int]:
    config = tomllib.loads((root / "pyproject.toml").read_text())
    return {key: int(value) for key, value in config["tool"]["shelf-size"].items()}


def problems(root: Path, paths: Iterable[str], caps: dict[str, int]) -> list[str]:
    found = []
    for rel in paths:
        size, funcs = measure((root / rel).read_text(encoding="utf-8"))
        cap = caps["test-file"] if "tests" in rel.split("/") else caps["code-file"]
        if size > cap:
            found.append(f"{rel}: {size} SLOC > {cap}")
        found.extend(f"{rel}:{name}: {size} SLOC > {caps['function']}" for name, size in funcs.items() if size > caps["function"])
    return found
