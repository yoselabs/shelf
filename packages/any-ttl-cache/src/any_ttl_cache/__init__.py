"""The sqlite TTL table, owned once: expiry, lazy eviction on read, an injected clock.

Stop re-writing "a row that stops being true after N seconds". :class:`TtlTable`
describes one table (its key columns, its value columns, the column that records when a
row was written, and the schema the caller owns) and does every read and write of it:
``put`` stamps ``expires_at = now + ttl_s``, ``get`` returns a fresh row or ``None`` and
deletes expired rows on the read that finds one, ``evict_expired`` and ``count`` finish
the surface. Time comes from an injected ``clock`` (seconds, ``time.time`` by default), so
a test steps time instead of sleeping.

The table is *policy-free*: what the key means, how a value is encoded (gzip, a
completion, an ETag) stays with the caller. The caller also owns the schema text, so the
bytes of an existing database never depend on this package; ``ensure`` checks that the
schema really has the declared columns plus ``expires_at``.

Connection-agnostic: the caller injects an open :class:`aiosqlite.Connection` into every
call. The table never opens or closes one, so it can share a file with other tables.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    import aiosqlite

#: The expiry column every TTL table carries, an integer second.
EXPIRES = "expires_at"

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class Entry:
    """One fresh row: its value columns in declared order, when it was written, when it expires."""

    # sqlite columns are dynamically typed; each caller narrows its own values.
    values: tuple[Any, ...]  # Any: sqlite's own dynamic column types
    stamped: int
    expires_at: int


def _identifier(kind: str, name: str) -> str:
    if not _IDENTIFIER.fullmatch(name):
        msg = f"{kind} {name!r} is not a plain sql identifier"
        raise ValueError(msg)
    return name


class TtlTable:
    """Reads and writes one TTL table; nothing else in the repo may touch its expiry."""

    def __init__(
        self,
        *,
        name: str,
        keys: Sequence[str],
        values: Sequence[str],
        stamped: str,
        schema: str,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Describe the table.

        Args:
            name: The table name.
            keys: The primary-key columns, in the order ``get`` and ``put`` take them.
            values: The payload columns, in the order ``put`` takes them and ``Entry`` returns them.
            stamped: The integer column that records the second a row was written.
            schema: The caller's ``CREATE TABLE`` and ``CREATE INDEX`` statements, ``IF NOT EXISTS``.
            clock: Seconds since the epoch; inject a fake to step time.
        """
        if not keys:
            msg = "a TTL table needs at least one key column"
            raise ValueError(msg)
        self._name = _identifier("table", name)
        self._keys = tuple(_identifier("key column", k) for k in keys)
        self._values = tuple(_identifier("value column", v) for v in values)
        self._stamped = _identifier("stamp column", stamped)
        self._schema = schema
        self._clock = clock
        columns = (*self._keys, *self._values, self._stamped, EXPIRES)
        where = " AND ".join(f"{k}=?" for k in self._keys)
        read = ", ".join((*self._values, self._stamped, EXPIRES))
        self._select = f"SELECT {read} FROM {self._name} WHERE {where} LIMIT 1"
        self._insert = f"INSERT OR REPLACE INTO {self._name} ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})"
        self._delete_expired = f"DELETE FROM {self._name} WHERE {EXPIRES} <= ?"
        self._count = f"SELECT COUNT(*) FROM {self._name}"
        self._required = frozenset(columns)

    async def ensure(self, conn: aiosqlite.Connection) -> None:
        """Create the table and indexes if missing, then check the declared columns exist. Idempotent."""
        await conn.executescript(self._schema)
        await conn.commit()
        async with conn.execute(f"PRAGMA table_info({self._name})") as cursor:
            present = {str(row[1]) for row in await cursor.fetchall()}
        missing = sorted(self._required - present)
        if missing:
            msg = f"table {self._name} lacks declared columns {missing}"
            raise ValueError(msg)

    async def get(self, conn: aiosqlite.Connection, key: Sequence[object]) -> Entry | None:
        """Return the fresh row under ``key``, else ``None``.

        A row is fresh while ``expires_at`` is after now. An expired row found here is
        deleted on this read, along with every other expired row.
        """
        self._check_key(key)
        now = int(self._clock())
        async with conn.execute(self._select, tuple(key)) as cursor:
            record = await cursor.fetchone()
        if record is None:
            return None
        if int(record[-1]) <= now:
            await self._evict(conn, now)
            return None
        return Entry(values=tuple(record[: len(self._values)]), stamped=int(record[-2]), expires_at=int(record[-1]))

    async def put(self, conn: aiosqlite.Connection, key: Sequence[object], values: Sequence[object], *, ttl_s: int) -> None:
        """Insert or replace the row under ``key``; it expires ``ttl_s`` seconds from now."""
        self._check_key(key)
        if len(values) != len(self._values):
            msg = f"table {self._name} takes {len(self._values)} values, got {len(values)}"
            raise ValueError(msg)
        now = int(self._clock())
        await conn.execute(self._insert, (*key, *values, now, now + ttl_s))
        await conn.commit()

    async def evict_expired(self, conn: aiosqlite.Connection) -> int:
        """Delete every expired row now. Returns the number removed."""
        return await self._evict(conn, int(self._clock()))

    async def count(self, conn: aiosqlite.Connection) -> int:
        """Return the row count, expired rows included."""
        async with conn.execute(self._count) as cursor:
            record = await cursor.fetchone()
        return int(record[0]) if record else 0

    async def _evict(self, conn: aiosqlite.Connection, now: int) -> int:
        cursor = await conn.execute(self._delete_expired, (now,))
        await conn.commit()
        return cursor.rowcount or 0

    def _check_key(self, key: Sequence[object]) -> None:
        if len(key) != len(self._keys):
            msg = f"table {self._name} has a {len(self._keys)}-column key, got {len(key)}"
            raise ValueError(msg)


__all__ = ["EXPIRES", "Entry", "TtlTable"]
