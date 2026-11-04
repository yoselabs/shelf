from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, override

import pytest
from sqlite_store import SharedConnections

if TYPE_CHECKING:
    from sqlite_store import Store


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
