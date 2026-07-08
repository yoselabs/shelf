"""Lazy async sqlite connection lifecycle — open once, on first use, under a lock.

:class:`SqliteResource` wraps an :mod:`aiosqlite` connection with lazy first-use
open, an internal lock so concurrent callers race safely, an idempotent close, and
the async context-manager protocol. Schema and pragma setup are caller-supplied, so
the primitive stays domain-free: it knows how to *manage a connection*, never what
tables live inside it.

The app stops caring about aiosqlite's open/close plumbing, the double-checked lazy
lock, and the "warm eagerly on lifespan, but never open in a test that doesn't touch
the DB" dance — it just holds a resource and reads ``.conn``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Self

import aiosqlite

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType

OnOpen = Callable[[aiosqlite.Connection], Awaitable[None]]
"""Optional hook run once, right after the connection opens (e.g. apply a schema)."""

_DEFAULT_PRAGMAS: tuple[str, ...] = ("journal_mode=WAL",)


class SqliteResource:
    """A lazily-opened aiosqlite connection with an async-CM lifecycle.

    The connection opens on the first :meth:`ensure` (or ``async with``) under an
    internal lock, applies ``pragmas`` and the optional ``on_open`` hook, then stays
    warm until :meth:`close`. Every operation is idempotent: re-entering, double-open
    and double-close are all safe.
    """

    def __init__(
        self,
        db_path: Path,
        *,
        pragmas: Sequence[str] = _DEFAULT_PRAGMAS,
        on_open: OnOpen | None = None,
    ) -> None:
        """Configure the resource; no I/O happens until :meth:`ensure`.

        Args:
            db_path: Filesystem path to the sqlite database. Parent directories are
                created on open.
            pragmas: ``PRAGMA`` bodies applied in order on open (e.g. ``journal_mode=WAL``).
            on_open: Optional coroutine run once after open — the place to apply a
                schema or seed rows. Kept caller-side so the primitive is domain-free.
        """
        self._db_path = db_path
        self._pragmas = tuple(pragmas)
        self._on_open = on_open
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def ensure(self) -> aiosqlite.Connection:
        """Return the open connection, opening it on first call (idempotent)."""
        if self._conn is not None:
            return self._conn
        async with self._lock:
            if self._conn is None:
                self._conn = await self._open()
            return self._conn

    async def _open(self) -> aiosqlite.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(self._db_path)
        for pragma in self._pragmas:
            await conn.execute(f"PRAGMA {pragma}")
        if self._on_open is not None:
            await self._on_open(conn)
        await conn.commit()
        return conn

    @property
    def conn(self) -> aiosqlite.Connection:
        """The open connection.

        Raises:
            RuntimeError: If accessed before :meth:`ensure` has opened the connection.
        """
        if self._conn is None:
            msg = "SqliteResource.conn accessed before ensure() opened the connection"
            raise RuntimeError(msg)
        return self._conn

    async def close(self) -> None:
        """Close the connection if open; a no-op otherwise (idempotent)."""
        if self._conn is None:
            return
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None

    async def __aenter__(self) -> Self:
        """Enter the context, opening the connection eagerly."""
        await self.ensure()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit the context, closing the connection."""
        await self.close()


__all__ = ("OnOpen", "SqliteResource")
