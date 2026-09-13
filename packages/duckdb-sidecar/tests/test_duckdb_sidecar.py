from __future__ import annotations

import contextlib
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
import pytest
from duckdb_sidecar import connect, is_lock_conflict, rename_column

if TYPE_CHECKING:
    from collections.abc import Generator


def test_connect_creates_missing_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deeper" / "store.duckdb"
    assert not target.parent.exists()

    conn = connect(target)
    try:
        assert target.parent.is_dir()
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        row = conn.execute("SELECT count(*) FROM t").fetchone()
        assert row is not None
        assert row[0] == 1
    finally:
        conn.close()


def test_connect_in_memory_touches_no_filesystem(tmp_path: Path) -> None:
    conn = connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (x INTEGER)")
        row = conn.execute("SELECT count(*) FROM t").fetchone()
        assert row is not None
        assert row[0] == 0
        # nothing was written under the working tree
        assert not any(tmp_path.iterdir())
        assert not Path(":memory:").exists()
    finally:
        conn.close()


def test_connect_reopen_keeps_data(tmp_path: Path) -> None:
    target = tmp_path / "store.duckdb"
    conn = connect(target)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.close()

    reopened = connect(target)
    try:
        row = reopened.execute("SELECT x FROM t").fetchone()
        assert row is not None
        assert row[0] == 42
    finally:
        reopened.close()


def test_connect_accepts_str_path(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "store.duckdb"
    conn = connect(str(target))
    try:
        assert target.parent.is_dir()
    finally:
        conn.close()


# --- is_lock_conflict ---------------------------------------------------
#
# The signature this function matches is a substring of a vendor message, so a
# test that builds the exception by hand proves only that the substring matches
# itself. These spawn a second interpreter, let it take the write lock, and read
# the real failure — which is the only thing that can tell us the day a DuckDB
# upgrade rewords it.

_HOLD_LOCK = "import sys, duckdb; c = duckdb.connect(sys.argv[1]); print('ready', flush=True); sys.stdin.readline()"


@contextlib.contextmanager
def _another_process_holding(target: Path) -> Generator[None]:
    """Run a second interpreter that opens ``target`` and keeps it open."""
    proc = subprocess.Popen(
        [sys.executable, "-c", _HOLD_LOCK, str(target)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "ready"
        yield
    finally:
        if proc.stdin is not None:
            proc.stdin.close()
        proc.wait(timeout=10)


def test_is_lock_conflict_recognizes_a_real_second_writer(tmp_path: Path) -> None:
    target = tmp_path / "store.duckdb"
    connect(target).close()

    with _another_process_holding(target), pytest.raises(duckdb.IOException) as caught:
        connect(target)

    assert is_lock_conflict(caught.value)


def test_is_lock_conflict_leaves_other_io_failures_alone(tmp_path: Path) -> None:
    """A missing-or-unreadable file is the same exception class and must not match."""
    unreadable = tmp_path / "not-a-database.duckdb"
    unreadable.write_text("this is not a duckdb file", encoding="utf-8")

    with pytest.raises(duckdb.Error) as caught:
        connect(unreadable)

    assert not is_lock_conflict(caught.value)


def test_is_lock_conflict_is_false_for_a_lookalike_message() -> None:
    """Narrow by class as well as by text: only DuckDB's own IO failure qualifies."""
    assert not is_lock_conflict(RuntimeError("Conflicting lock is held by someone"))


# --- rename_column ------------------------------------------------------


def test_rename_column_fails_without_the_helper(tmp_path: Path) -> None:
    """The hazard itself, pinned: DuckDB refuses the rename while an index exists."""
    conn = connect(tmp_path / "store.duckdb")
    try:
        conn.execute("CREATE TABLE node(id TEXT, kind TEXT)")
        conn.execute("CREATE INDEX node_by_id ON node(id)")

        with pytest.raises(duckdb.Error):
            conn.execute("ALTER TABLE node RENAME COLUMN kind TO type")
    finally:
        conn.close()


def test_rename_column_rebuilds_an_index_on_another_column(tmp_path: Path) -> None:
    conn = connect(tmp_path / "store.duckdb")
    try:
        conn.execute("CREATE TABLE edge(source TEXT, target TEXT, edge_kind TEXT)")
        conn.execute("CREATE INDEX edge_by_target ON edge(target)")
        conn.execute("INSERT INTO edge VALUES ('a', 'b', 'mentions')")

        assert rename_column(conn, table="edge", old="edge_kind", new="edge_type") is True

        assert conn.execute("SELECT edge_type FROM edge").fetchall() == [("mentions",)]
        assert _index_names(conn, "edge") == ["edge_by_target"]
    finally:
        conn.close()


def test_rename_column_rebuilds_an_index_over_the_renamed_column(tmp_path: Path) -> None:
    """The case a verbatim replay of the stored SQL would get wrong."""
    conn = connect(tmp_path / "store.duckdb")
    try:
        conn.execute("CREATE TABLE node(id TEXT, kind TEXT, weight INTEGER)")
        conn.execute("CREATE INDEX node_by_kind ON node(kind)")
        conn.execute("CREATE INDEX node_by_pair ON node(weight, kind)")
        conn.execute("INSERT INTO node VALUES ('n1', 'project', 3)")

        assert rename_column(conn, table="node", old="kind", new="type") is True

        assert conn.execute("SELECT type FROM node WHERE type = 'project'").fetchall() == [("project",)]
        assert _index_names(conn, "node") == ["node_by_kind", "node_by_pair"]
        assert "kind" not in _index_sql(conn, "node_by_pair")
        assert "type" in _index_sql(conn, "node_by_pair")
    finally:
        conn.close()


def test_rename_column_works_with_no_indexes_at_all(tmp_path: Path) -> None:
    conn = connect(tmp_path / "store.duckdb")
    try:
        conn.execute("CREATE TABLE node(kind TEXT)")

        assert rename_column(conn, table="node", old="kind", new="type") is True
        assert _column_names(conn, "node") == ["type"]
    finally:
        conn.close()


def test_rename_column_is_a_no_op_on_an_already_migrated_database(tmp_path: Path) -> None:
    """A store replays its migrations on every open; the second pass must do nothing."""
    conn = connect(tmp_path / "store.duckdb")
    try:
        conn.execute("CREATE TABLE node(type TEXT)")
        conn.execute("CREATE INDEX node_by_type ON node(type)")

        assert rename_column(conn, table="node", old="kind", new="type") is False
        assert _column_names(conn, "node") == ["type"]
        assert _index_names(conn, "node") == ["node_by_type"]
    finally:
        conn.close()


def test_rename_column_is_a_no_op_when_the_old_column_never_existed(tmp_path: Path) -> None:
    """A ladder where several old spellings converge on one new name takes only
    the branch that matches; the others must pass over a database they do not fit."""
    conn = connect(tmp_path / "store.duckdb")
    try:
        conn.execute("CREATE TABLE node(entity_type TEXT)")

        assert rename_column(conn, table="node", old="kind", new="type") is False
        assert rename_column(conn, table="node", old="entity_type", new="type") is True
        assert _column_names(conn, "node") == ["type"]
    finally:
        conn.close()


def test_rename_column_refuses_when_both_columns_are_there(tmp_path: Path) -> None:
    """Both present means the store's own history is ambiguous — do not guess."""
    conn = connect(tmp_path / "store.duckdb")
    try:
        conn.execute("CREATE TABLE node(kind TEXT, type TEXT)")

        with pytest.raises(ValueError, match="already exists"):
            rename_column(conn, table="node", old="kind", new="type")
    finally:
        conn.close()


def test_rename_column_leaves_a_string_inside_an_index_expression_alone(tmp_path: Path) -> None:
    """A rename moves identifiers; a string that merely spells one is data.

    DuckDB has no partial indexes (`CREATE INDEX ... WHERE` raises
    NotImplementedException as of 1.5), so an expression index is where a literal
    and an identifier sit side by side in the same statement.
    """
    conn = connect(tmp_path / "store.duckdb")
    try:
        conn.execute("CREATE TABLE node(kind TEXT, label TEXT)")
        conn.execute("CREATE INDEX node_by_labelling ON node(coalesce(label, 'kind'))")
        conn.execute("INSERT INTO node VALUES ('project', NULL)")

        assert rename_column(conn, table="node", old="kind", new="type") is True

        assert "'kind'" in _index_sql(conn, "node_by_labelling")
        assert conn.execute("SELECT type FROM node").fetchall() == [("project",)]
    finally:
        conn.close()


def _index_names(conn: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    rows = conn.execute("SELECT index_name FROM duckdb_indexes() WHERE table_name = ? ORDER BY index_name", [table]).fetchall()
    return [name for (name,) in rows]


def _index_sql(conn: duckdb.DuckDBPyConnection, index_name: str) -> str:
    row = conn.execute("SELECT sql FROM duckdb_indexes() WHERE index_name = ?", [index_name]).fetchone()
    assert row is not None
    return str(row[0])


def _column_names(conn: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()]
