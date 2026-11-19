from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest
import sqlite_store
from sqlite_sidecar import transaction
from sqlite_store import change_counter

if TYPE_CHECKING:
    from pathlib import Path

    from sqlite_store import Store


@pytest.mark.parametrize("failure", [ValueError, KeyboardInterrupt, SystemExit])
def test_commit_and_rollback_on_every_base_exception(tmp_path: Path, store: Store, failure: type[BaseException]) -> None:
    con = store.open_rw(tmp_path / "journal.db")
    assert con is not None
    try:
        with transaction(con):
            con.execute("INSERT INTO item VALUES ('kept', 'value', 0)")
        with pytest.raises(failure), transaction(con):
            con.execute("INSERT INTO item VALUES ('lost', 'value', 0)")
            raise failure
        assert con.execute("SELECT id FROM item").fetchall() == [("kept",)]
        assert not con.in_transaction
    finally:
        con.close()


def test_change_counter_and_wal_snapshot(tmp_path: Path, store: Store) -> None:
    path = tmp_path / "journal.db"
    writer = store.open_rw(path)
    reader = store.open_ro(path)
    assert writer is not None and reader is not None
    try:
        before_reader, before_writer = change_counter(reader), change_counter(writer)
        reader.execute("BEGIN")
        assert reader.execute("SELECT * FROM item").fetchall() == []
        with transaction(writer):
            writer.execute("INSERT INTO item VALUES ('a', 'value', 0)")
            assert change_counter(reader) == before_reader
        assert reader.execute("SELECT * FROM item").fetchall() == []
        reader.rollback()
        after_reader = change_counter(reader)
        assert after_reader != before_reader
        assert change_counter(writer) == before_writer
        with pytest.raises(ValueError), transaction(writer):
            writer.execute("DELETE FROM item")
            message = "abort"
            raise ValueError(message)
        assert change_counter(reader) == after_reader
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("DELETE FROM item")
    finally:
        reader.close()
        writer.close()


def test_store_does_not_carry_a_second_transaction_helper() -> None:
    assert not hasattr(sqlite_store, "begin_immediate")


def test_store_transaction_rolls_back_a_failed_commit_and_evicts_the_writer(tmp_path: Path, store: Store) -> None:
    con = store.shared_rw(tmp_path / "journal.db")
    assert con is not None
    con.execute("CREATE TABLE child(p TEXT REFERENCES item(id) DEFERRABLE INITIALLY DEFERRED)")
    with pytest.raises(sqlite3.IntegrityError), store.begin_immediate(con):
        con.execute("INSERT INTO child VALUES ('missing')")  # refused only at COMMIT
    with pytest.raises(sqlite3.ProgrammingError):  # a DatabaseError evicts and closes the cached writer
        con.execute("SELECT 1")
    fresh = store.open_rw(tmp_path / "journal.db")
    assert fresh is not None
    assert fresh.execute("SELECT count(*) FROM child").fetchone() == (0,)
    fresh.close()
