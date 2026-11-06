from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from threading import Barrier, Event
from typing import TYPE_CHECKING, Literal
from unittest.mock import Mock

import pytest
from sqlite_store import SchemaError, Store, open_ro, open_rw
from sqlite_store import store as store_module

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from sqlite_store import Schema


def test_creation_pragmas_and_idempotent_reopen(tmp_path: Path, schema: Schema) -> None:
    path = tmp_path / "journal.db"
    con = open_rw(path, schema)
    assert con is not None
    try:
        assert con.isolation_level is None
        pragmas = [("user_version", 2), ("journal_mode", "wal"), ("synchronous", 1), ("foreign_keys", 1), ("busy_timeout", 5000)]
        for pragma, expected in pragmas:
            assert con.execute(f"PRAGMA {pragma}").fetchone() == (expected,)
        con.execute("INSERT INTO item VALUES ('a', 'kept', 0)")
    finally:
        con.close()
    for opener in (open_rw, open_ro):
        reopened = opener(path, schema)
        assert reopened is not None
        try:
            assert reopened.execute("SELECT * FROM item").fetchall() == [("a", "kept", 0)]
        finally:
            reopened.close()


def test_older_reader_refuses_writer_upgrades_without_replacement(tmp_path: Path, schema: Schema) -> None:
    path = tmp_path / "journal.db"
    old = open_rw(path, schema)
    assert old is not None
    old.execute("INSERT INTO item VALUES ('a', 'kept', 0)")
    old.close()
    inode = path.stat().st_ino

    def step(con: sqlite3.Connection) -> None:
        con.execute("ALTER TABLE item ADD COLUMN summary TEXT")
        con.execute("UPDATE item SET summary=value")

    newer = replace(schema, version=3, steps={2: step})
    with pytest.raises(SchemaError, match=r"test journal is schema v2.*knows v3"):
        open_ro(path, newer)
    writer = open_rw(path, newer)
    assert writer is not None
    writer.close()
    reader = open_ro(path, newer)
    assert reader is not None
    try:
        assert reader.execute("SELECT summary FROM item").fetchall() == [("kept",)]
    finally:
        reader.close()
    assert path.stat().st_ino == inode
    assert list(tmp_path.glob("*.bad-*")) == []


def test_newer_database_and_missing_upgrade_raise(tmp_path: Path, schema: Schema) -> None:
    path = tmp_path / "journal.db"
    con = open_rw(path, schema)
    assert con is not None
    con.close()
    with pytest.raises(SchemaError, match="test journal missing upgrade step v2 -> v3"):
        open_rw(path, replace(schema, version=3))
    for opener in (open_rw, open_ro):
        with pytest.raises(SchemaError, match="test journal is schema v2, this code knows v1: update it"):
            opener(path, replace(schema, version=1, quarantine_versions=frozenset({2})))
    assert list(tmp_path.glob("*.bad-*")) == []


def test_failed_ddl_is_atomic(tmp_path: Path, schema: Schema) -> None:
    path = tmp_path / "journal.db"
    assert open_rw(path, replace(schema, ddl=schema.ddl + "INVALID SQL;")) is None
    con = sqlite3.connect(path)
    try:
        assert con.execute("PRAGMA user_version").fetchone() == (0,)
        assert con.execute("SELECT name FROM sqlite_master").fetchall() == []
    finally:
        con.close()


@pytest.mark.parametrize("state", ["missing", "corrupt", "nonempty", "missing-parent"])
def test_unavailable_storage_returns_none(tmp_path: Path, schema: Schema, state: str) -> None:
    path = tmp_path / "journal.db"
    if state == "corrupt":
        path.write_bytes(b"not SQLite")
    elif state == "nonempty":
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE unrelated (value TEXT)")
        con.close()
    elif state == "missing-parent":
        path = tmp_path / "absent" / "journal.db"
    if state == "nonempty":
        with pytest.raises(SchemaError, match="schema v0"):
            open_ro(path, schema)
    else:
        assert open_ro(path, schema) is None
    if state == "missing":
        assert not path.exists()
    else:
        assert open_rw(path, schema) is None


def test_wal_unavailable_refused(tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store_module, "_journal_mode", lambda *_args, **_kwargs: "delete")
    con = sqlite3.connect(":memory:", isolation_level=None)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="WAL unavailable"):
            store_module._configure(con, readonly=False)
    finally:
        con.close()
    assert store.open_rw(tmp_path / "journal.db") is None


def test_quick_check_cached_by_file_identity_and_never_readonly(tmp_path: Path, schema: Schema, monkeypatch: pytest.MonkeyPatch) -> None:
    statements: list[str] = []
    connect = sqlite3.connect

    def traced(
        database: str,
        *,
        uri: bool = False,
        isolation_level: Literal["DEFERRED", "EXCLUSIVE", "IMMEDIATE"] | None = None,
        timeout: float = 5.0,
        check_same_thread: bool = True,
    ) -> sqlite3.Connection:
        con = connect(database, uri=uri, isolation_level=isolation_level, timeout=timeout, check_same_thread=check_same_thread)
        con.set_trace_callback(statements.append)
        return con

    monkeypatch.setattr(sqlite3, "connect", traced)
    path = tmp_path / "journal.db"
    store = Store(schema)
    for opener in (store.open_rw, store.open_rw, store.open_ro):
        con = opener(path)
        assert con is not None
        con.close()
    assert statements.count("PRAGMA quick_check") == 1
    statements.clear()
    other_process = Store(schema)
    for opener in (other_process.open_ro, other_process.open_rw, other_process.open_rw):
        con = opener(path)
        assert con is not None
        con.close()
    assert statements.count("PRAGMA quick_check") == 1
    assert statements.count("PRAGMA user_version") == 3
    assert "PRAGMA journal_mode=WAL" not in statements
    path.rename(tmp_path / "old.db")
    con = store.open_rw(path)
    assert con is not None
    con.close()
    assert statements.count("PRAGMA quick_check") == 2


def test_failed_extra_check_is_not_cached_and_readers_skip_it(tmp_path: Path, schema: Schema, monkeypatch: pytest.MonkeyPatch) -> None:
    # Extra integrity queries have the same one-row 'ok' contract as quick_check.
    store = Store(replace(schema, checks=("SELECT 'damaged'",)))
    path = tmp_path / "journal.db"
    assert store.open_rw(path) is None
    assert store.open_rw(path) is None
    normal = Store(schema)
    writer = normal.open_rw(path)
    assert writer is not None
    writer.close()
    reader = store.open_ro(path)
    assert reader is not None
    reader.close()
    probe = Mock(return_value=True)
    monkeypatch.setattr(store_module, "filesystem_allowed", probe)
    assert store.open_rw(path) is None
    probe.assert_called_once_with(tmp_path)


def test_concurrent_creation(tmp_path: Path, schema: Schema, monkeypatch: pytest.MonkeyPatch) -> None:
    ready = Barrier(2, timeout=10)
    begin = store_module.begin_immediate

    @contextmanager
    def synchronized(con: sqlite3.Connection) -> Generator[None]:
        ready.wait()
        with begin(con):
            yield

    monkeypatch.setattr(store_module, "begin_immediate", synchronized)

    def opener() -> int:
        con = open_rw(tmp_path / "journal.db", schema)
        assert con is not None
        try:
            return int(con.execute("PRAGMA user_version").fetchone()[0])
        finally:
            con.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(opener), pool.submit(opener)
        assert [first.result(timeout=15), second.result(timeout=15)] == [2, 2]


def test_readonly_open_of_an_uninitialised_file_is_none_not_a_schema_error(tmp_path: Path, schema: Schema) -> None:
    path = tmp_path / "journal.db"
    path.touch()  # a writer has created the file and not yet run the DDL
    assert open_ro(path, schema) is None
    sqlite3.connect(path).execute("CREATE TABLE foreign_table (a)").connection.close()
    with pytest.raises(SchemaError, match="schema v0"):  # a v0 file with tables is someone else's, not a creation in progress
        open_ro(path, schema)


def test_reader_during_first_creation_sees_not_there_yet(tmp_path: Path, schema: Schema, monkeypatch: pytest.MonkeyPatch) -> None:
    inside, release = Event(), Event()
    begin = store_module.begin_immediate

    @contextmanager
    def paused(con: sqlite3.Connection) -> Generator[None]:
        inside.set()  # the file exists at user_version 0; the DDL has not run
        assert release.wait(timeout=10)
        with begin(con):
            yield

    monkeypatch.setattr(store_module, "begin_immediate", paused)
    def create() -> int:
        con = open_rw(tmp_path / "journal.db", schema)
        assert con is not None
        try:
            return int(con.execute("PRAGMA user_version").fetchone()[0])
        finally:
            con.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        writer = pool.submit(create)
        assert inside.wait(timeout=10)
        assert open_ro(tmp_path / "journal.db", schema) is None
        release.set()
        assert writer.result(timeout=15) == schema.version
    reader = open_ro(tmp_path / "journal.db", schema)
    assert reader is not None
    reader.close()


def test_filesystem_refusal_prevents_connect(tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    connect = Mock(side_effect=AssertionError("must refuse before connecting"))
    monkeypatch.setattr(store_module, "filesystem_allowed", lambda _parent: False)
    monkeypatch.setattr(sqlite3, "connect", connect)
    assert store.open_rw(tmp_path / "journal.db") is None
    assert store.open_ro(tmp_path / "journal.db") is None
    connect.assert_not_called()


def test_bad_quick_check_is_rejected_without_caching(tmp_path: Path, schema: Schema) -> None:
    path = tmp_path / "journal.db"
    path.touch()
    checked: set[store_module.Identity] = set()
    con = Mock(spec=sqlite3.Connection)
    con.execute.return_value.fetchall.return_value = [("damaged",)]
    for _ in range(2):
        with pytest.raises(sqlite3.DatabaseError, match="integrity check failed"):
            store_module._check_integrity(con, path, schema, checked, created=False, readonly=False)
    assert checked == set()
    assert con.execute.call_count == 2


def test_journal_mode_retry_window(monkeypatch: pytest.MonkeyPatch) -> None:
    con = Mock(spec=sqlite3.Connection)
    old_mode, new_mode = Mock(), Mock()
    old_mode.fetchone.return_value = ("delete",)
    new_mode.fetchone.return_value = ("wal",)
    con.execute.side_effect = [sqlite3.OperationalError("database is locked"), old_mode, new_mode]
    monkeypatch.setattr(store_module.time, "monotonic", Mock(side_effect=[0.0, 1.0]))
    pause = Mock()
    monkeypatch.setattr(store_module.time, "sleep", pause)
    assert store_module._journal_mode(con, readonly=False) == "wal"
    pause.assert_called_once_with(0.01)
    con.execute.side_effect = sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(store_module.time, "monotonic", Mock(side_effect=[0.0, 5.0]))
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        store_module._journal_mode(con, readonly=False)
