from __future__ import annotations

import atexit
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Thread
from typing import TYPE_CHECKING, override
from unittest.mock import Mock

import pytest
from sqlite_store import SharedConnections, Store

if TYPE_CHECKING:
    from sqlite_store import Schema


def test_shared_reuse_aliases_threads_and_close(tmp_path: Path, store: Store) -> None:
    path = tmp_path / "journal.db"
    con = store.shared_rw(path)
    assert con is not None
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path, target_is_directory=True)
    assert store.shared_rw(alias / path.name) is con

    def in_thread() -> sqlite3.Connection:
        other = store.shared_rw(path)
        assert other is not None
        assert store.shared_rw(path) is other
        return other

    with ThreadPoolExecutor(max_workers=1) as pool:
        other = pool.submit(in_thread).result(timeout=10)
    assert other is not con
    store.close_shared()
    for closed in (con, other):
        with pytest.raises(sqlite3.ProgrammingError):
            closed.execute("SELECT 1")
    assert store.shared_rw(path) is not con


def test_replaced_inode_is_not_reused(tmp_path: Path, store: Store) -> None:
    path, replacement = tmp_path / "journal.db", tmp_path / "replacement.db"
    old, other = store.shared_rw(path), store.open_rw(replacement)
    assert old is not None and other is not None
    other.execute("INSERT INTO item VALUES ('new', 'value', 0)")
    other.close()
    for suffix in ("", "-wal", "-shm"):
        Path(str(path) + suffix).unlink(missing_ok=True)
    replacement.rename(path)
    fresh = store.shared_rw(path)
    assert fresh is not None and fresh is not old
    assert fresh.execute("SELECT id FROM item").fetchall() == [("new",)]
    with pytest.raises(sqlite3.ProgrammingError):
        old.execute("SELECT 1")


@pytest.mark.parametrize("state", ["closed", "unfinished", "deleted"])
def test_stale_writer_is_replaced(tmp_path: Path, store: Store, state: str) -> None:
    path = tmp_path / "journal.db"
    old = store.shared_rw(path)
    assert old is not None
    if state == "closed":
        old.close()
    elif state == "unfinished":
        old.execute("BEGIN IMMEDIATE")
        old.execute("INSERT INTO item VALUES ('lost', 'value', 0)")
    else:
        path.unlink()
    fresh = store.shared_rw(path)
    assert fresh is not None and fresh is not old
    assert fresh.execute("SELECT * FROM item").fetchall() == []


@pytest.mark.parametrize("stage", ["begin", "body", "commit"])
def test_database_error_discards_shared_writer(tmp_path: Path, store: Store, stage: str, monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenCommit(sqlite3.Connection):
        @override
        def commit(self) -> None:
            message = "commit failed"
            raise sqlite3.DatabaseError(message)

    path = tmp_path / "journal.db"
    initial = store.open_rw(path)
    assert initial is not None
    initial.close()
    if stage == "commit":
        connect = sqlite3.connect

        def broken(target: Path) -> sqlite3.Connection:
            return connect(target, isolation_level=None, check_same_thread=False, factory=BrokenCommit)

        # Shared opens deliberately use their own cross-thread-close connection factory.
        def open_broken(_path: str | os.PathLike[str], *, readonly: bool, shared: bool = False) -> sqlite3.Connection:
            return broken(path)

        monkeypatch.setattr(store, "_open", open_broken)
    con = store.shared_rw(path)
    assert con is not None
    if stage == "begin":
        con.execute("BEGIN IMMEDIATE")
    with pytest.raises(sqlite3.DatabaseError), store.begin_immediate(con):
        con.execute("INSERT INTO item VALUES ('lost', 'value', 0)")
        if stage == "body":
            message = "database disk image is malformed"
            raise sqlite3.DatabaseError(message)
    with pytest.raises(sqlite3.ProgrammingError):
        con.execute("SELECT 1")
    monkeypatch.undo()
    fresh = store.shared_rw(path)
    assert fresh is not None and fresh is not con
    assert fresh.execute("SELECT * FROM item").fetchall() == []


def test_pid_ownership_and_after_fork(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = SharedConnections()
    path = tmp_path / "journal.db"

    def opener(target: Path) -> sqlite3.Connection:
        return sqlite3.connect(target, isolation_level=None, check_same_thread=False)

    parent = cache.get(path, opener)
    assert parent is not None
    pid = os.getpid()
    with monkeypatch.context() as child_patch:
        child_patch.setattr(os, "getpid", lambda: pid + 1)
        cache.after_fork()
        child = cache.get(path, opener)
        assert child is not None and child is not parent
        cache.discard(parent)
        cache.close()
        with pytest.raises(sqlite3.ProgrammingError):
            child.execute("SELECT 1")
        assert parent.execute("SELECT 1").fetchone() == (1,)
    assert cache.get(path, opener) is parent
    cache.discard(parent)
    assert cache.get(path, opener) is not parent
    cache.close()


def test_short_lived_threads_release_writers(tmp_path: Path, store: Store) -> None:
    fd_directory = Path("/proc/self/fd")
    if not fd_directory.is_dir():
        pytest.skip("Linux fd accounting required")
    baseline = sum(1 for _ in fd_directory.iterdir())
    path = tmp_path / "journal.db"
    errors: list[BaseException] = []

    def write(start: Event) -> None:
        try:
            assert start.wait(timeout=300)
            con = store.shared_rw(path)
            assert con is not None
            con.execute("INSERT INTO item VALUES (lower(hex(randomblob(16))), 'kept', 0)")
        except (AssertionError, sqlite3.Error, OSError, RuntimeError) as error:
            errors.append(error)

    # Keep all identities alive initially so OS thread-id reuse cannot mask leaks.
    starts = [Event() for _ in range(200)]
    workers = [(start, Thread(target=write, args=(start,))) for start in starts]
    for _, thread in workers:
        thread.start()
    try:
        for start, thread in workers:
            start.set()
            thread.join(timeout=30)
            assert not thread.is_alive()
    finally:
        for start, _ in workers:
            start.set()
        for _, thread in workers:
            thread.join(timeout=30)
    assert not errors
    con = store.shared_rw(path)
    assert con is not None
    assert con.execute("SELECT count(*) FROM item").fetchone() == (200,)
    assert len(store._shared.connections) <= 2
    assert sum(1 for _ in fd_directory.iterdir()) <= baseline + 5
    store.close_shared()
    assert sum(1 for _ in fd_directory.iterdir()) <= baseline + 2


def test_store_creation_does_not_register_exit_or_fork_callbacks(schema: Schema, monkeypatch: pytest.MonkeyPatch) -> None:
    exit_registration, fork_registration = Mock(), Mock()
    monkeypatch.setattr(atexit, "register", exit_registration)
    monkeypatch.setattr(os, "register_at_fork", fork_registration)
    stores = [Store(schema) for _ in range(50)]
    assert len(stores) == 50
    exit_registration.assert_not_called()
    fork_registration.assert_not_called()


def test_last_shared_close_cleans_wal(tmp_path: Path, store: Store) -> None:
    path = tmp_path / "journal.db"
    con = store.shared_rw(path)
    assert con is not None
    con.execute("INSERT INTO item VALUES ('a', 'kept', 0)")
    assert Path(str(path) + "-wal").stat().st_size > 0
    store.close_shared()
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        assert not sidecar.exists() or sidecar.stat().st_size == 0
    reader = store.open_ro(path)
    assert reader is not None
    try:
        assert reader.execute("SELECT value FROM item").fetchall() == [("kept",)]
    finally:
        reader.close()


def test_process_exit_closes_shared_writer(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    script = """
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[2])
from sqlite_store import Schema, Store

store = Store(Schema(version=1, ddl="CREATE TABLE item (value TEXT)", steps={}))
path = Path(sys.argv[1])
con = store.shared_rw(path)
assert con is not None
con.execute("INSERT INTO item VALUES ('kept')")
assert Path(str(path) + "-wal").stat().st_size > 0
"""
    source = Path(__file__).resolve().parents[1] / "src"
    result = subprocess.run([sys.executable, "-c", script, str(path), str(source)], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    for suffix in ("-wal", "-shm"):
        assert not Path(str(path) + suffix).exists()
    reader = sqlite3.connect(path)
    try:
        assert reader.execute("SELECT value FROM item").fetchall() == [("kept",)]
    finally:
        reader.close()
