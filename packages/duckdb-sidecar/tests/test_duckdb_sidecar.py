from __future__ import annotations

from pathlib import Path

from duckdb_sidecar import connect


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
