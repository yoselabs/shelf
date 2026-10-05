"""The SQLite sidecar plumbing: open, transact, the timestamp codec, damage vs busy."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import threading
from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest
import sqlite_sidecar as sc

if TYPE_CHECKING:
    from pathlib import Path


def test_a_file_target_creates_its_parent_and_opens_in_wal(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deep" / "store.sqlite"
    conn = sc.connect(target)
    try:
        assert target.parent.is_dir()
        assert conn.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert conn.isolation_level is None, "autocommit: transactions are explicit"
    finally:
        conn.close()


def test_memory_touches_no_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    conn = sc.connect(":memory:")
    conn.execute("CREATE TABLE t(x)")
    conn.close()
    assert list(tmp_path.iterdir()) == []


def test_an_extension_that_fails_to_load_is_named(tmp_path: Path) -> None:
    def broken(conn: sqlite3.Connection) -> None:
        msg = "no such extension"
        raise sqlite3.OperationalError(msg)

    with pytest.raises(sc.ExtensionUnavailableError) as caught:
        sc.connect(tmp_path / "s.sqlite", extensions={"zephyr_vec": broken})
    assert caught.value.extension == "zephyr_vec"


def test_an_extension_loader_runs_on_the_connection(tmp_path: Path) -> None:
    seen: list[sqlite3.Connection] = []
    conn = sc.connect(tmp_path / "s.sqlite", extensions={"probe": seen.append})
    assert seen == [conn]
    conn.close()


def test_a_read_only_open_reads_the_last_commit_and_refuses_a_write(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    writer = sc.connect(path)
    writer.execute("CREATE TABLE t(x)")
    writer.execute("INSERT INTO t VALUES (1)")
    reader = sc.connect(path, read_only=True)
    try:
        assert reader.execute("SELECT x FROM t").fetchall() == [(1,)]
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            reader.execute("INSERT INTO t VALUES (2)")
        writer.execute("INSERT INTO t VALUES (3)")
        assert reader.execute("SELECT x FROM t ORDER BY x").fetchall() == [(1,), (3,)]
    finally:
        reader.close()
        writer.close()


# --- transactions -------------------------------------------------------------------


def test_a_transaction_commits_or_rolls_back_whole(tmp_path: Path) -> None:
    conn = sc.connect(tmp_path / "s.sqlite")
    conn.execute("CREATE TABLE t(x)")
    with sc.transaction(conn):
        conn.execute("INSERT INTO t VALUES (1)")
    with pytest.raises(RuntimeError), sc.transaction(conn):
        conn.execute("INSERT INTO t VALUES (2)")
        raise RuntimeError
    assert conn.execute("SELECT x FROM t").fetchall() == [(1,)]
    assert not conn.in_transaction
    conn.close()


def test_a_nested_transaction_is_a_savepoint(tmp_path: Path) -> None:
    conn = sc.connect(tmp_path / "s.sqlite")
    conn.execute("CREATE TABLE t(x)")
    with sc.transaction(conn):
        conn.execute("INSERT INTO t VALUES (1)")
        with pytest.raises(RuntimeError), sc.transaction(conn):
            conn.execute("INSERT INTO t VALUES (2)")
            raise RuntimeError
        conn.execute("INSERT INTO t VALUES (3)")
    assert conn.execute("SELECT x FROM t ORDER BY x").fetchall() == [(1,), (3,)]
    conn.close()


def test_a_transaction_holds_the_lock_it_is_given(tmp_path: Path) -> None:
    conn = sc.connect(tmp_path / "s.sqlite")
    lock = threading.RLock()
    with sc.transaction(conn, lock=lock):
        acquired = threading.Event()

        def other() -> None:
            if lock.acquire(blocking=False):
                acquired.set()
                lock.release()

        t = threading.Thread(target=other)
        t.start()
        t.join()
        assert not acquired.is_set()
    assert lock.acquire(blocking=False)
    lock.release()
    conn.close()


# --- the timestamp codec ----------------------------------------------------------


def _naive(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0, micro: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, micro)  # noqa: DTZ001 — a naive value is UTC by contract


def test_text_is_fixed_width_utc() -> None:
    assert sc.to_text(_naive(2026, 7, 1)) == "2026-07-01 00:00:00.000000"
    assert sc.to_text(_naive(987, 1, 2, 3, 4, 5, 6)) == "0987-01-02 03:04:05.000006"
    plus3 = timezone(timedelta(hours=3))
    assert sc.to_text(datetime(2026, 7, 1, 3, 0, tzinfo=plus3)) == "2026-07-01 00:00:00.000000"


def test_text_reads_back_naive_or_utc_aware() -> None:
    value = _naive(2026, 7, 1, 12, 30, 15, 250)
    assert sc.from_text(sc.to_text(value)) == value
    aware = datetime(2026, 7, 1, 12, 30, tzinfo=UTC)
    assert sc.from_text(sc.to_text(aware), aware=True) == aware
    assert sc.from_text(sc.to_text(aware), aware=True).tzinfo is UTC


def test_text_order_is_time_order() -> None:
    times = [_naive(2026, 7, 1, 0, 0, 0, 1), _naive(999, 12, 31), _naive(2026, 7, 1), _naive(9999, 1, 1)]
    assert sorted(times, key=sc.to_text) == sorted(times)


# --- damage -----------------------------------------------------------------------


def test_not_a_database_is_corruption_and_busy_is_not(tmp_path: Path) -> None:
    bad = tmp_path / "bad.sqlite"
    bad.write_bytes(b"fictional bytes that are not a database" * 100)
    conn = sqlite3.connect(bad)
    with pytest.raises(sqlite3.DatabaseError) as caught:
        conn.execute("SELECT * FROM sqlite_master").fetchall()
    conn.close()
    assert sc.is_corruption(caught.value)

    path = tmp_path / "s.sqlite"
    holder = sc.connect(path)
    holder.execute("CREATE TABLE t(x)")
    holder.execute("BEGIN IMMEDIATE")
    other = sqlite3.connect(path, timeout=0, isolation_level=None)
    with pytest.raises(sqlite3.OperationalError) as busy:
        other.execute("BEGIN IMMEDIATE")
    other.close()
    holder.execute("ROLLBACK")
    holder.close()
    assert not sc.is_corruption(busy.value)
    assert not sc.is_corruption(ValueError("corrupt"))


def test_unreadable_is_true_only_for_a_file_that_is_not_a_database(tmp_path: Path) -> None:
    assert not sc.unreadable(tmp_path / "absent.sqlite")
    good = tmp_path / "good.sqlite"
    sc.connect(good).close()
    assert not sc.unreadable(good)
    bad = tmp_path / "bad.sqlite"
    bad.write_bytes(b"x" * 4096)
    assert sc.unreadable(bad)


def test_integrity_runs_its_extra_check_on_a_fresh_connection(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    conn = sc.connect(path)
    conn.execute("CREATE TABLE t(x)")
    conn.close()
    assert sc.integrity_ok(path)

    def fails(c: sqlite3.Connection) -> None:
        msg = "extra check failed"
        raise sqlite3.DatabaseError(msg)

    assert not sc.integrity_ok(path, extra=fails)
    bad = tmp_path / "bad.sqlite"
    bad.write_bytes(b"x" * 4096)
    assert not sc.integrity_ok(bad)


def test_set_aside_moves_the_file_with_its_wal_and_shm(tmp_path: Path) -> None:
    db = tmp_path / "graph.sqlite"
    for p in (db, tmp_path / "graph.sqlite-wal", tmp_path / "graph.sqlite-shm"):
        p.write_bytes(b"fictional")
    moved = sc.set_aside(db, at=datetime(2026, 10, 2, 12, 0, tzinfo=UTC))
    assert sorted(p.name for p in moved) == [
        "graph.sqlite-shm.corrupt-20261002T120000Z",
        "graph.sqlite-wal.corrupt-20261002T120000Z",
        "graph.sqlite.corrupt-20261002T120000Z",
    ]
    assert not db.exists()


def test_another_process_reads_the_last_commit_while_a_write_is_open(tmp_path: Path) -> None:
    """WAL: a read-only open in a second process sees the last commit, never waits."""
    path = tmp_path / "s.sqlite"
    writer = sc.connect(path)
    writer.execute("CREATE TABLE t(x)")
    writer.execute("INSERT INTO t VALUES (1)")
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("INSERT INTO t VALUES (2)")
    probe = (
        "import sys, sqlite_sidecar as sc\n"
        "c = sc.connect(sys.argv[1], read_only=True, timeout=0)\n"
        "print(c.execute('SELECT count(*) FROM t').fetchone()[0])\n"
    )
    out = subprocess.run([sys.executable, "-c", probe, str(path)], capture_output=True, text=True, check=True, timeout=30)
    writer.execute("COMMIT")
    writer.close()
    assert out.stdout.strip() == "1"
