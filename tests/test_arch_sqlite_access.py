"""One SQLite access path (Article III): `sqlite3.connect` is called only inside the sqlite-* packages.

Every other caller opens through sqlite-sidecar (`connect`) or sqlite-store (`open_rw`/`open_ro`).
Static AST scan of non-test code, no runtime cost. The rule has no rows: no other caller exists today.
"""

from __future__ import annotations

import ast
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from any_arch import Rule, check, plant

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent
_OWNERS = ("sqlite-sidecar", "sqlite-store")


def _connect_calls(source: Source) -> Iterator[Hit]:
    """Lines calling `sqlite3.connect(...)`, or `connect(...)` imported from sqlite3; the owners, tests and hidden folders are skipped."""
    parts = PurePosixPath(source.rel).parts
    if "tests" in parts or any(p.startswith(".") or p in {"node_modules", "__pycache__"} for p in parts) or source.package in _OWNERS:
        return
    from_sqlite3 = {
        alias.asname or alias.name
        for node in ast.walk(source.tree)
        if isinstance(node, ast.ImportFrom) and node.module == "sqlite3"
        for alias in node.names
        if alias.name == "connect"
    }
    for node in ast.walk(source.tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        direct = (
            isinstance(func, ast.Attribute) and func.attr == "connect" and isinstance(func.value, ast.Name) and func.value.id == "sqlite3"
        )
        if direct or (isinstance(func, ast.Name) and func.id in from_sqlite3):
            yield source.rel, node.lineno


SQLITE_CONNECT = Rule(
    "sqlite-connect",
    "open through sqlite-sidecar `connect` or sqlite-store, not sqlite3.connect",
    _connect_calls,
    {},
    scope=("packages/**/*.py", "tools/**/*.py", "skills/**/*.py"),
)


def test_sqlite_connect_lives_in_the_sqlite_packages_only() -> None:
    check(SQLITE_CONNECT, _ROOT)


def test_the_scan_sees_a_direct_and_an_imported_connect(tmp_path: Path) -> None:
    where = "packages/pkg/src/pkg/mod.py"
    assert plant(SQLITE_CONNECT, tmp_path / "a", "import sqlite3\nsqlite3.connect('x')", where) == {where: [2]}
    assert plant(SQLITE_CONNECT, tmp_path / "b", "from sqlite3 import connect as c\nc('x')", where) == {where: [2]}
    assert plant(SQLITE_CONNECT, tmp_path / "c", "import sqlite3\nother.connect('x')", where) == {}


def test_the_owners_and_the_tests_are_not_scanned(tmp_path: Path) -> None:
    source = "import sqlite3\nsqlite3.connect('x')"
    assert plant(SQLITE_CONNECT, tmp_path / "a", source, "packages/sqlite-store/src/sqlite_store/mod.py") == {}
    assert plant(SQLITE_CONNECT, tmp_path / "b", source, "tools/tests/mod.py") == {}
