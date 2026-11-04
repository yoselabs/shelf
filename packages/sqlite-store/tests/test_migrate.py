from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import TYPE_CHECKING

import pytest
from sqlite_store import SchemaError, Step, upgrade

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture
def con(tmp_path: Path) -> Generator[sqlite3.Connection]:
    connection = sqlite3.connect(tmp_path / "journal.db", isolation_level=None)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE item (id TEXT PRIMARY KEY, value TEXT)")
    connection.execute("INSERT INTO item VALUES ('a', 'old')")
    connection.execute("PRAGMA user_version=2")
    yield connection
    connection.close()


def add_summary(con: sqlite3.Connection) -> None:
    con.execute("ALTER TABLE item ADD COLUMN summary TEXT")
    con.execute("UPDATE item SET summary=value || ':backfilled'")


def test_order_backfill_and_idempotence(con: sqlite3.Connection) -> None:
    observed: list[int] = []

    def next_step(connection: sqlite3.Connection) -> None:
        observed.append(connection.execute("PRAGMA user_version").fetchone()[0])
        connection.execute("UPDATE item SET summary=summary || ':upgraded'")

    upgrade(con, {2: add_summary, 3: next_step}, 2, 4, name="test journal")
    assert observed == [3]
    assert con.execute("SELECT * FROM item").fetchall() == [("a", "old", "old:backfilled:upgraded")]
    assert con.execute("PRAGMA user_version").fetchone() == (4,)
    upgrade(con, {}, 2, 4)
    assert not con.in_transaction


@pytest.mark.parametrize("failure", ["missing", "failing"])
def test_entire_chain_rolls_back(con: sqlite3.Connection, failure: str) -> None:
    def fail(connection: sqlite3.Connection) -> None:
        connection.execute("UPDATE item SET value='lost'")
        message = "backfill failed"
        raise ValueError(message)

    steps: dict[int, Step] = {2: add_summary}
    if failure == "failing":
        steps[3] = fail
    message = "test journal .*step v3 -> v4"
    with pytest.raises(SchemaError, match=message) as raised:
        upgrade(con, steps, 2, 4, name="test journal")
    if failure == "failing":
        assert isinstance(raised.value.__cause__, ValueError)
        assert "backfill failed" in str(raised.value)
    assert con.execute("PRAGMA user_version").fetchone() == (2,)
    assert con.execute("SELECT * FROM item").fetchall() == [("a", "old")]
    assert not con.in_transaction


def test_newer_schema_refused_by_name(con: sqlite3.Connection) -> None:
    with pytest.raises(SchemaError, match="test journal is schema v2, this code knows v1: update it"):
        upgrade(con, {}, 0, 1, name="test journal")
    assert con.execute("PRAGMA user_version").fetchone() == (2,)
    with pytest.raises(SchemaError, match="database is schema v2"):
        upgrade(con, {}, 0, 1)


def test_racing_upgraders_apply_once(con: sqlite3.Connection, tmp_path: Path) -> None:
    ready = Barrier(2, timeout=10)
    calls: list[int] = []

    def step(connection: sqlite3.Connection) -> None:
        calls.append(1)
        add_summary(connection)

    def opener() -> int:
        connection = sqlite3.connect(tmp_path / "journal.db", isolation_level=None, timeout=5)
        try:
            ready.wait()
            upgrade(connection, {2: step}, 2, 3)
            return int(connection.execute("PRAGMA user_version").fetchone()[0])
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(opener), pool.submit(opener)
        assert [first.result(timeout=15), second.result(timeout=15)] == [3, 3]
    assert calls == [1]
    assert con.execute("SELECT summary FROM item").fetchone() == ("old:backfilled",)
