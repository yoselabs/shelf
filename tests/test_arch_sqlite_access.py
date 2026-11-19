"""One SQLite access path (Article III): `sqlite3.connect` is called only inside the sqlite-* packages.

Every other caller opens through sqlite-sidecar (`connect`) or sqlite-store (`open_rw`/`open_ro`).
Static AST scan of non-test code, no runtime cost. The allowlist below holds today's other callers.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_OWNERS = ("sqlite-sidecar", "sqlite-store")

# consumer wave empties this: each entry is a caller to repoint at sqlite-sidecar's `connect`.
_ALLOWED = {
    "packages/anyembed/src/anyembed/cache.py",
    "packages/fts-query/src/fts_query/__init__.py",
}


def _connect_calls(tree: ast.AST) -> list[int]:
    """Lines calling `sqlite3.connect(...)`, or `connect(...)` imported from sqlite3."""
    from_sqlite3 = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "sqlite3"
        for alias in node.names
        if alias.name == "connect"
    }
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        direct = (
            isinstance(func, ast.Attribute) and func.attr == "connect" and isinstance(func.value, ast.Name) and func.value.id == "sqlite3"
        )
        if direct or (isinstance(func, ast.Name) and func.id in from_sqlite3):
            lines.append(node.lineno)
    return lines


def _callers() -> set[str]:
    found: set[str] = set()
    for base in ("packages", "tools", "skills"):
        for path in (_ROOT / base).rglob("*.py"):
            rel = path.relative_to(_ROOT)
            parts = rel.parts
            if "tests" in parts or any(p.startswith(".") or p in {"node_modules", "__pycache__"} for p in parts):
                continue
            if parts[0] == "packages" and parts[1] in _OWNERS:
                continue
            if _connect_calls(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
                found.add(rel.as_posix())
    return found


def test_sqlite_connect_lives_in_the_sqlite_packages_only() -> None:
    offenders = sorted(_callers() - _ALLOWED)
    assert offenders == [], f"open through sqlite-sidecar `connect` or sqlite-store, not sqlite3.connect: {offenders}"


def test_the_allowlist_has_no_stale_entries() -> None:
    assert sorted(_ALLOWED - _callers()) == [], "remove the entry: that file no longer calls sqlite3.connect"


def test_the_scan_sees_a_direct_and_an_imported_connect() -> None:
    assert _connect_calls(ast.parse("import sqlite3\nsqlite3.connect('x')")) == [2]
    assert _connect_calls(ast.parse("from sqlite3 import connect as c\nc('x')")) == [2]
    assert _connect_calls(ast.parse("import sqlite3\nother.connect('x')")) == []
