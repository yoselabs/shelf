from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest
from sqlite_store import begin_immediate, change_counter

if TYPE_CHECKING:
    from pathlib import Path

    from sqlite_store import Store


@pytest.mark.parametrize("failure", [ValueError, KeyboardInterrupt, SystemExit])
def test_commit_and_rollback_on_every_base_exception(tmp_path: Path, store: Store, failure: type[BaseException]) -> None:
    con = store.open_rw(tmp_path / "journal.db")
    assert con is not None
    try:
        with begin_immediate(con):
            con.execute("INSERT INTO item VALUES ('kept', 'value', 0)")
        with pytest.raises(failure), begin_immediate(con):
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
        with begin_immediate(writer):
            writer.execute("INSERT INTO item VALUES ('a', 'value', 0)")
            assert change_counter(reader) == before_reader
        assert reader.execute("SELECT * FROM item").fetchall() == []
        reader.rollback()
        after_reader = change_counter(reader)
        assert after_reader != before_reader
        assert change_counter(writer) == before_writer
        with pytest.raises(ValueError), begin_immediate(writer):
            writer.execute("DELETE FROM item")
            message = "abort"
            raise ValueError(message)
        assert change_counter(reader) == after_reader
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("DELETE FROM item")
    finally:
        reader.close()
        writer.close()
