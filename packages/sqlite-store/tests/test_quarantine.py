from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import TYPE_CHECKING
from unittest.mock import Mock

from sqlite_store import Store, quarantine
from sqlite_store import store as store_module

if TYPE_CHECKING:
    import pytest
    from sqlite_store import Schema


def test_quarantine_moves_database_and_sidecars(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    for suffix in ("", "-wal", "-shm"):
        Path(str(path) + suffix).write_bytes(suffix.encode() or b"database")
    bad = quarantine(path)
    assert bad.name.startswith("journal.db.bad-")
    for suffix in ("", "-wal", "-shm"):
        assert not Path(str(path) + suffix).exists()
        assert Path(str(bad) + suffix).read_bytes() == (suffix.encode() or b"database")


def test_old_derived_schema_is_quarantined_and_recreated(tmp_path: Path, schema: Schema) -> None:
    path = tmp_path / "journal.db"
    old = sqlite3.connect(path, isolation_level=None)
    old.execute("CREATE TABLE derived (value TEXT)")
    old.execute("INSERT INTO derived VALUES ('preserved')")
    old.execute("PRAGMA user_version=1")
    old.close()
    store = Store(schema)
    fresh = store.open_rw(path)
    assert fresh is not None
    fresh.close()
    archived = list(tmp_path.glob("journal.db.bad-*"))
    assert len(archived) == 1
    old = sqlite3.connect(archived[0])
    try:
        assert old.execute("SELECT * FROM derived").fetchall() == [("preserved",)]
        assert old.execute("PRAGMA user_version").fetchone() == (1,)
    finally:
        old.close()
    assert (tmp_path / "journal.db.schema.lock").exists()


def test_racing_openers_quarantine_only_once(tmp_path: Path, schema: Schema, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "journal.db"
    old = sqlite3.connect(path, isolation_level=None)
    old.execute("PRAGMA user_version=1")
    old.close()
    ready = Barrier(2, timeout=10)
    retire = store_module.quarantine_if_needed
    calls = Mock(wraps=retire)

    def synchronized(target: Path, versions: frozenset[int]) -> None:
        ready.wait()
        calls(target, versions)

    monkeypatch.setattr(store_module, "quarantine_if_needed", synchronized)

    def opener() -> int:
        con = Store(schema).open_rw(path)
        assert con is not None
        try:
            assert con.execute("SELECT * FROM item").fetchall() == []
            return int(con.execute("PRAGMA user_version").fetchone()[0])
        finally:
            con.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(opener), pool.submit(opener)
        assert [first.result(timeout=15), second.result(timeout=15)] == [2, 2]
    assert calls.call_count == 2
    assert len(list(tmp_path.glob("journal.db.bad-*"))) == 1
