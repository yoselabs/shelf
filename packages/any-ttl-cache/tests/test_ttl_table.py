"""TtlTable: expiry, lazy eviction and the injected clock, over an in-memory sqlite."""

from __future__ import annotations

import aiosqlite
import pytest

from any_ttl_cache import Entry, TtlTable

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    topic     TEXT NOT NULL,
    lang      TEXT NOT NULL,
    body      TEXT NOT NULL,
    written   INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    PRIMARY KEY (topic, lang)
);
"""


class FakeClock:
    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _table(clock: FakeClock) -> TtlTable:
    return TtlTable(name="notes", keys=("topic", "lang"), values=("body",), stamped="written", schema=_SCHEMA, clock=clock)


@pytest.fixture
async def conn():
    connection = await aiosqlite.connect(":memory:")
    try:
        yield connection
    finally:
        await connection.close()


async def test_miss_is_none(conn) -> None:
    table = _table(FakeClock())
    await table.ensure(conn)
    assert await table.get(conn, ("a", "en")) is None


async def test_put_then_get_returns_values_and_both_timestamps(conn) -> None:
    clock = FakeClock(1_000.9)  # the stored second is the integer part
    table = _table(clock)
    await table.ensure(conn)
    await table.put(conn, ("a", "en"), ("hello",), ttl_s=60)
    assert await table.get(conn, ("a", "en")) == Entry(values=("hello",), stamped=1_000, expires_at=1_060)


async def test_entry_is_fresh_until_the_expiry_second_and_gone_at_it(conn) -> None:
    clock = FakeClock(1_000)
    table = _table(clock)
    await table.ensure(conn)
    await table.put(conn, ("a", "en"), ("x",), ttl_s=10)
    clock.now = 1_009
    assert await table.get(conn, ("a", "en")) is not None
    clock.now = 1_010
    assert await table.get(conn, ("a", "en")) is None


async def test_keys_are_independent_slots(conn) -> None:
    table = _table(FakeClock())
    await table.ensure(conn)
    await table.put(conn, ("a", "en"), ("english",), ttl_s=60)
    await table.put(conn, ("a", "ru"), ("russian",), ttl_s=60)
    entry = await table.get(conn, ("a", "ru"))
    assert entry is not None
    assert entry.values == ("russian",)


async def test_put_replaces_the_same_key(conn) -> None:
    table = _table(FakeClock())
    await table.ensure(conn)
    await table.put(conn, ("a", "en"), ("old",), ttl_s=60)
    await table.put(conn, ("a", "en"), ("new",), ttl_s=60)
    entry = await table.get(conn, ("a", "en"))
    assert entry is not None
    assert entry.values == ("new",)
    assert await table.count(conn) == 1


async def test_reading_an_expired_entry_evicts_it_and_every_other_expired_row(conn) -> None:
    clock = FakeClock(1_000)
    table = _table(clock)
    await table.ensure(conn)
    await table.put(conn, ("old1", "en"), ("a",), ttl_s=5)
    await table.put(conn, ("old2", "en"), ("b",), ttl_s=5)
    await table.put(conn, ("live", "en"), ("c",), ttl_s=500)
    clock.now = 1_100
    assert await table.get(conn, ("old1", "en")) is None
    assert await table.count(conn) == 1


async def test_a_fresh_read_evicts_nothing(conn) -> None:
    clock = FakeClock(1_000)
    table = _table(clock)
    await table.ensure(conn)
    await table.put(conn, ("old", "en"), ("a",), ttl_s=5)
    await table.put(conn, ("live", "en"), ("c",), ttl_s=500)
    clock.now = 1_100
    assert await table.get(conn, ("live", "en")) is not None
    assert await table.count(conn) == 2


async def test_evict_expired_returns_the_count(conn) -> None:
    clock = FakeClock(1_000)
    table = _table(clock)
    await table.ensure(conn)
    for i in range(3):
        await table.put(conn, (f"k{i}", "en"), ("v",), ttl_s=0)
    await table.put(conn, ("live", "en"), ("v",), ttl_s=100)
    assert await table.evict_expired(conn) == 3
    assert await table.count(conn) == 1


async def test_a_negative_ttl_is_born_expired(conn) -> None:
    table = _table(FakeClock())
    await table.ensure(conn)
    await table.put(conn, ("a", "en"), ("x",), ttl_s=-1)
    assert await table.get(conn, ("a", "en")) is None


async def test_ensure_is_idempotent(conn) -> None:
    table = _table(FakeClock())
    await table.ensure(conn)
    await table.put(conn, ("a", "en"), ("x",), ttl_s=60)
    await table.ensure(conn)
    assert await table.count(conn) == 1


async def test_a_schema_missing_a_declared_column_is_refused(conn) -> None:
    table = TtlTable(
        name="notes",
        keys=("topic",),
        values=("body", "missing"),
        stamped="written",
        schema=_SCHEMA,
        clock=FakeClock(),
    )
    with pytest.raises(ValueError, match="missing"):
        await table.ensure(conn)


def test_identifiers_are_validated_because_they_are_spliced_into_sql() -> None:
    with pytest.raises(ValueError, match="identifier"):
        TtlTable(name="notes; DROP TABLE x", keys=("topic",), values=("body",), stamped="written", schema=_SCHEMA)


def test_a_table_needs_a_key() -> None:
    with pytest.raises(ValueError, match="key"):
        TtlTable(name="notes", keys=(), values=("body",), stamped="written", schema=_SCHEMA)


async def test_a_key_of_the_wrong_length_is_refused(conn) -> None:
    table = _table(FakeClock())
    await table.ensure(conn)
    with pytest.raises(ValueError, match="key"):
        await table.get(conn, ("only-one",))
    with pytest.raises(ValueError, match="values"):
        await table.put(conn, ("a", "en"), ("x", "y"), ttl_s=1)
