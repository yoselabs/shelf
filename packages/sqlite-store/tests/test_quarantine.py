from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from threading import Barrier
from typing import TYPE_CHECKING
from unittest.mock import Mock

from sqlite_store import Store, quarantine
from sqlite_store import store as store_module

if TYPE_CHECKING:
    from multiprocessing.synchronize import Barrier as ProcessBarrier

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


def _process_quarantine(path: Path, schema: Schema, ready: ProcessBarrier, opened: ProcessBarrier) -> None:
    retire = store_module.quarantine_if_needed
    prepare = store_module._schema_ready

    def synchronized(path: Path, versions: frozenset[int]) -> None:
        # Both processes must observe v1 and close their probes before flock.
        ready.wait(timeout=60)
        retire(path, versions)

    def counted(con: sqlite3.Connection, schema: Schema, version: int, *, readonly: bool) -> bool:
        created = prepare(con, schema, version, readonly=readonly)
        if created:
            # Exclusive creation also catches a second initialization in this process.
            with path.with_name(f"created-{os.getpid()}").open("x", encoding="utf-8") as marker:
                marker.write("created")
        return created

    store_module.quarantine_if_needed = synchronized
    store_module._schema_ready = counted
    con = Store(schema).open_rw(path)
    assert con is not None
    try:
        opened.wait(timeout=60)
        assert con.execute("PRAGMA user_version").fetchone() == (schema.version,)
        assert con.execute("PRAGMA quick_check").fetchall() == [("ok",)]
        assert con.execute("SELECT * FROM item").fetchall() == []
        path.with_name(f"opened-{os.getpid()}").write_text(str(path.stat().st_ino), encoding="utf-8")
    finally:
        con.close()


def test_processes_quarantine_and_create_exactly_once(tmp_path: Path, schema: Schema) -> None:
    path = tmp_path / "journal.db"
    old = sqlite3.connect(path, isolation_level=None)
    try:
        old.execute("CREATE TABLE derived (value TEXT)")
        old.execute("INSERT INTO derived VALUES ('preserved'), ('also preserved')")
        old.execute("PRAGMA user_version=1")
    finally:
        old.close()
    context = get_context("spawn")
    ready, opened = context.Barrier(2), context.Barrier(2)
    processes = [context.Process(target=_process_quarantine, args=(path, schema, ready, opened)) for _ in range(2)]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=90)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            if process.pid is not None:
                process.join(timeout=30)
    archives = [entry for entry in tmp_path.glob("journal.db.bad-*") if not entry.name.endswith(("-wal", "-shm"))]
    assert len(archives) == 1
    groups = {entry.name.removesuffix("-wal").removesuffix("-shm") for entry in tmp_path.glob("journal.db.bad-*")}
    assert groups == {archives[0].name}
    assert len(list(tmp_path.glob("created-*"))) == 1
    reports = list(tmp_path.glob("opened-*"))
    assert len(reports) == 2
    assert {report.read_text(encoding="utf-8") for report in reports} == {str(path.stat().st_ino)}
    archived = sqlite3.connect(archives[0])
    try:
        assert archived.execute("PRAGMA user_version").fetchone() == (1,)
        assert archived.execute("SELECT * FROM derived").fetchall() == [
            ("preserved",),
            ("also preserved",),
        ]
    finally:
        archived.close()
