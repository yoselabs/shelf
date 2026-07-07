#!/usr/bin/env python3
"""Architectural fitness rules — the native reimplementation of a2kit's Rego policies.

Resolution 0005: the shelf models architecture-fitness as pure-stdlib Python (like
``tests/test_boundary.py``), NOT as OPA/Rego — OPA is a non-hermetic binary substrate
the shelf exists to shed. This engine is the shared machinery; the blocking assertions
live in ``tests/test_arch_rules.py`` and the non-blocking cross-package report in
``tools/arch_advisory.py``.

Three rules (a2kit lineage in parens):
- **dep upper-bound** (RG004): every runtime dependency must declare an upper bound.
- **body duplication** (RG001): two functions in different files with the same
  *normalized* body (alpha-equivalent — local names + literals abstracted).
- **private-name collision** (RG002): a ``_``-prefixed helper name reused across files.

Scope matters (constitution VI values *some* duplication): the tests block only
**within a package**; **across packages** duplication is advisory — a "consider a T0
primitive" nudge, never a build failure.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PACKAGES = _ROOT / "packages"
_ALLOWLIST = _ROOT / "tests" / "arch_allowlist.toml"

_MIN_DUP_STMTS = 3  # trivial 1-2 statement collisions (return x, raise X) are out of scope

FuncDef = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class FunctionFact:
    """One function's identity + a normalized fingerprint of its body."""

    package: str
    file: str
    name: str
    line: int
    is_private: bool
    is_dunder: bool
    stmt_count: int
    body_hash: str


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _local_names(fn: FuncDef) -> set[str]:
    """Names bound locally in a function: its args plus every assignment target."""
    names: set[str] = set()
    args = fn.args
    for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
        names.add(arg.arg)
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return names


class _Normalizer(ast.NodeTransformer):
    """Alpha-equivalence normalizer for function bodies.

    Renames local identifiers + abstracts literals so two functions that differ only in
    variable names / constant values hash the same. Call targets, attributes, and global
    names are KEPT — they are the logic, not the naming.
    """

    def __init__(self, local_names: set[str]) -> None:
        self._locals = local_names
        self._canon: dict[str, str] = {}

    def _token(self, name: str) -> str:
        return self._canon.setdefault(name, f"L{len(self._canon)}")

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in self._locals:
            return ast.copy_location(ast.Name(id=self._token(node.id), ctx=node.ctx), node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:
        new = ast.arg(arg=self._token(node.arg), annotation=None)
        return ast.copy_location(new, node)

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        return ast.copy_location(ast.Constant(value=type(node.value).__name__), node)


def _body_without_docstring(fn: FuncDef) -> list[ast.stmt]:
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def _stmt_count(nodes: list[ast.stmt]) -> int:
    return sum(1 for node in nodes for sub in ast.walk(node) if isinstance(sub, ast.stmt))


def _body_hash(fn: FuncDef) -> str:
    normalizer = _Normalizer(_local_names(fn))
    parts: list[str] = []
    for stmt in _body_without_docstring(fn):
        normalized = normalizer.visit(copy.deepcopy(stmt))
        parts.append(ast.dump(ast.fix_missing_locations(normalized)))
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def function_facts() -> list[FunctionFact]:
    """Every function defined in every package's ``src/`` tree, with a normalized body hash."""
    facts: list[FunctionFact] = []
    for src in sorted(_PACKAGES.glob("*/src/*")):
        if not src.is_dir():
            continue
        for path in sorted(src.rglob("*.py")):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                body = _body_without_docstring(node)
                facts.append(
                    FunctionFact(
                        package=src.name,
                        file=str(path.relative_to(_ROOT)),
                        name=node.name,
                        line=node.lineno,
                        is_private=node.name.startswith("_") and not _is_dunder(node.name),
                        is_dunder=_is_dunder(node.name),
                        stmt_count=_stmt_count(body),
                        body_hash=_body_hash(node),
                    )
                )
    return facts


def _in_scope(a: FunctionFact, b: FunctionFact, *, cross_package: bool) -> bool:
    if a.file == b.file:
        return False
    same_package = a.package == b.package
    return (not same_package) if cross_package else same_package


def body_dups(facts: list[FunctionFact], *, cross_package: bool) -> list[tuple[FunctionFact, FunctionFact]]:
    """Pairs of non-dunder functions in different files sharing a normalized body."""
    out: list[tuple[FunctionFact, FunctionFact]] = []
    for i, a in enumerate(facts):
        for b in facts[i + 1 :]:
            if a.is_dunder or b.is_dunder:
                continue
            if a.stmt_count < _MIN_DUP_STMTS or b.stmt_count < _MIN_DUP_STMTS:
                continue
            if a.body_hash != b.body_hash:
                continue
            if _in_scope(a, b, cross_package=cross_package):
                out.append((a, b))
    return out


def name_collisions(facts: list[FunctionFact], *, cross_package: bool) -> list[tuple[FunctionFact, FunctionFact]]:
    """Pairs of private (``_``-prefixed, non-dunder) functions reusing a name across files."""
    out: list[tuple[FunctionFact, FunctionFact]] = []
    for i, a in enumerate(facts):
        for b in facts[i + 1 :]:
            if not (a.is_private and b.is_private):
                continue
            if a.name != b.name:
                continue
            if _in_scope(a, b, cross_package=cross_package):
                out.append((a, b))
    return out


def dep_name(spec: str) -> str:
    """The bare distribution name from a PEP 508 requirement string."""
    for i, ch in enumerate(spec):
        if ch in "[<>=!~; (":
            return spec[:i].strip()
    return spec.strip()


def _has_upper_bound(spec: str) -> bool:
    return any(token in spec for token in ("<", "~=", "==", "==="))


def unbounded_deps() -> list[tuple[str, str]]:
    """(package, spec) for every runtime dependency lacking an upper bound (RG004)."""
    out: list[tuple[str, str]] = []
    for pyproject in sorted(_PACKAGES.glob("*/pyproject.toml")):
        data = tomllib.loads(pyproject.read_text())
        project = data.get("project", {})
        package = str(project.get("name", pyproject.parent.name))
        out.extend((package, str(spec)) for spec in project.get("dependencies", []) if not _has_upper_bound(str(spec)))
    return out


def load_allowlist() -> dict[str, object]:
    """The architectural-rule allowlist (every entry must carry a reason — RG003)."""
    if not _ALLOWLIST.exists():
        return {}
    return tomllib.loads(_ALLOWLIST.read_text())
