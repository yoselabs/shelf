"""A derived store is set aside and rebuilt, never repaired."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlite_sidecar import MARK_SUFFIX, connect, ensure_schema, mark_for_rebuild, needs_rebuild, prepare, set_aside

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _store(path: Path) -> None:
    conn = connect(path)
    conn.execute("CREATE TABLE t (x)")
    conn.close()


def test_a_mark_survives_until_the_store_is_set_aside(tmp_path: Path) -> None:
    path = tmp_path / "index.sqlite"
    _store(path)
    assert not needs_rebuild(path)
    mark_for_rebuild(path, reason="index drift")
    assert needs_rebuild(path)
    assert "index drift" in (tmp_path / f"index.sqlite{MARK_SUFFIX}").read_text(encoding="utf-8")
    moved = set_aside(path, at=_AT)
    assert [p.name for p in moved] == ["index.sqlite.corrupt-20260102T030405Z"]
    assert not needs_rebuild(path)
    assert not path.exists()


def test_marking_an_in_memory_store_is_a_noop(tmp_path: Path) -> None:
    mark_for_rebuild(None)
    assert list(tmp_path.iterdir()) == []


def test_prepare_leaves_a_healthy_store_alone(tmp_path: Path) -> None:
    path = tmp_path / "index.sqlite"
    _store(path)
    assert prepare(path) == []
    assert prepare(tmp_path / "absent.sqlite") == []
    assert path.exists()


def test_prepare_sets_aside_a_marked_store(tmp_path: Path) -> None:
    path = tmp_path / "index.sqlite"
    _store(path)
    mark_for_rebuild(path)
    assert len(prepare(path)) == 1
    assert not path.exists()
    assert not needs_rebuild(path)


def test_prepare_sets_aside_a_file_that_is_not_a_database(tmp_path: Path) -> None:
    path = tmp_path / "index.sqlite"
    path.write_bytes(b"not a database at all, just bytes" * 200)
    assert len(prepare(path)) == 1
    conn = connect(path)  # the open after it starts empty
    assert conn.execute("SELECT count(*) FROM sqlite_master").fetchone() == (0,)
    conn.close()


_V1 = "CREATE TABLE node (id TEXT PRIMARY KEY);\nCREATE INDEX node_id ON node (id);\n"
_V2 = "CREATE TABLE node (id TEXT PRIMARY KEY, title TEXT);\n"


def _tables(conn: sqlite3.Connection) -> list[str]:
    return sorted(name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'"))


def test_ensure_schema_creates_then_keeps_a_current_file(tmp_path: Path) -> None:
    conn = connect(tmp_path / "g.sqlite")
    assert ensure_schema(conn, version=1, script=_V1) is True
    conn.execute("INSERT INTO node VALUES ('a')")
    assert ensure_schema(conn, version=1, script=_V1) is False
    assert conn.execute("SELECT count(*) FROM node").fetchone() == (1,)
    assert _tables(conn) == ["node", "schema_meta"]


def test_ensure_schema_empties_a_file_from_another_version(tmp_path: Path) -> None:
    conn = connect(tmp_path / "g.sqlite")
    ensure_schema(conn, version=1, script=_V1)
    conn.execute("INSERT INTO node VALUES ('a')")
    conn.execute("CREATE TABLE extra (y)")  # a table the new script does not know is dropped too
    assert ensure_schema(conn, version=2, script=_V2) is True
    assert conn.execute("SELECT count(*) FROM node").fetchone() == (0,)
    assert [c[1] for c in conn.execute("PRAGMA table_info(node)")] == ["id", "title"]
    assert _tables(conn) == ["node", "schema_meta"]
    assert conn.execute("SELECT schema_version FROM schema_meta").fetchall() == [(2,)]


def test_ensure_schema_over_tables_with_no_version_rebuilds(tmp_path: Path) -> None:
    conn = connect(tmp_path / "g.sqlite")
    conn.execute("CREATE TABLE node (legacy)")
    assert ensure_schema(conn, version=1, script=_V1) is True
    assert [c[1] for c in conn.execute("PRAGMA table_info(node)")] == ["id"]


def test_a_script_may_create_schema_meta_itself(tmp_path: Path) -> None:
    conn = connect(tmp_path / "g.sqlite")
    script = "CREATE TABLE IF NOT EXISTS schema_meta (schema_version INTEGER PRIMARY KEY);\n" + _V1
    assert ensure_schema(conn, version=3, script=script) is True
    assert ensure_schema(conn, version=3, script=script) is False
