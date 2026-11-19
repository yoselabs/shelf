"""Conditional-GET HTTP response cache on sqlite — ETag / Last-Modified / TTL / gzip.

The app stops caring about the mechanics of an HTTP cache: content-hash dedup, a
gzip-compressed body column, TTL expiry, and the ``(url, variant)`` primary key that
lets one URL cache differently per request profile. Backed by
:class:`sqlite_resource.SqliteResource` (schema applied via its ``on_open`` hook).

The ``variant`` key is a caller-supplied cache-variant string (a hash of whatever the
response varies by — proxy profile, auth, ``Accept-Language``); pass ``""`` when a URL
caches uniformly. Conditional-GET request headers are produced by
:func:`conditional_headers` from a stored row; a ``304`` means "reuse the stored body".
"""

from __future__ import annotations

import gzip
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from any_ttl_cache import TtlTable
from content_digest import digest_bytes
from sqlite_resource import SqliteResource

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    url            TEXT NOT NULL,
    variant        TEXT NOT NULL,
    etag           TEXT,
    last_modified  TEXT,
    fetched_at     INTEGER NOT NULL,
    expires_at     INTEGER NOT NULL,
    status_code    INTEGER NOT NULL,
    content_type   TEXT,
    content_hash   TEXT NOT NULL,
    body           BLOB NOT NULL,
    PRIMARY KEY (url, variant)
);
"""

_INDEX = "CREATE INDEX IF NOT EXISTS cache_content_hash ON cache(content_hash);"


def _table(clock: Callable[[], float]) -> TtlTable:
    return TtlTable(
        name="cache",
        keys=("url", "variant"),
        values=("etag", "last_modified", "status_code", "content_type", "content_hash", "body"),
        stamped="fetched_at",
        schema=_SCHEMA + _INDEX,
        clock=clock,
    )


@dataclass(slots=True, frozen=True)
class CacheRow:
    """One cached HTTP response. ``body`` is the decompressed payload."""

    url: str
    variant: str
    etag: str | None
    last_modified: str | None
    fetched_at: int
    expires_at: int
    status_code: int
    content_type: str | None
    content_hash: str
    body: bytes


async def apply_schema(conn: aiosqlite.Connection) -> None:
    """Create the cache table + index if absent — an :class:`SqliteResource` ``on_open`` hook."""
    await _table(time.time).ensure(conn)


def conditional_headers(row: CacheRow | None) -> dict[str, str]:
    """Build ``If-None-Match`` / ``If-Modified-Since`` headers from a stored row."""
    if row is None:
        return {}
    out: dict[str, str] = {}
    if row.etag:
        out["If-None-Match"] = row.etag
    if row.last_modified:
        out["If-Modified-Since"] = row.last_modified
    return out


async def cache_get(conn: aiosqlite.Connection, url: str, variant: str = "", *, clock: Callable[[], float] = time.time) -> CacheRow | None:
    """Return a non-expired row for ``(url, variant)``, or ``None``."""
    entry = await _table(clock).get(conn, (url, variant))
    if entry is None:
        return None
    etag, last_modified, status_code, content_type, content_hash, body = entry.values
    return CacheRow(
        url=url,
        variant=variant,
        etag=etag,
        last_modified=last_modified,
        fetched_at=entry.stamped,
        expires_at=entry.expires_at,
        status_code=status_code,
        content_type=content_type,
        content_hash=content_hash,
        body=gzip.decompress(body),
    )


async def cache_put(
    conn: aiosqlite.Connection,
    url: str,
    variant: str = "",
    *,
    etag: str | None,
    last_modified: str | None,
    status_code: int,
    content_type: str | None,
    body: bytes,
    ttl_s: int,
    clock: Callable[[], float] = time.time,
) -> None:
    """Insert or replace one row. The caller decides *whether* to cache (gate first)."""
    await _table(clock).put(
        conn,
        (url, variant),
        (etag, last_modified, status_code, content_type, digest_bytes(body, length=64), gzip.compress(body)),
        ttl_s=ttl_s,
    )


class HttpCache:
    """A conditional-GET HTTP cache over one sqlite database.

    Thin policy-free store: :meth:`get` returns a live row (or ``None``), :meth:`put`
    writes one. Composes :class:`sqlite_resource.SqliteResource` for the connection
    lifecycle and applies the cache schema on open.
    """

    def __init__(self, db_path: Path, *, clock: Callable[[], float] = time.time) -> None:
        """Bind the cache to ``db_path`` (opened lazily on first use); ``clock`` is seconds since the epoch."""
        self._res = SqliteResource(db_path, on_open=apply_schema)
        self._clock = clock

    async def get(self, url: str, variant: str = "") -> CacheRow | None:
        """Return the non-expired cached response for ``(url, variant)``, or ``None``."""
        conn = await self._res.ensure()
        return await cache_get(conn, url, variant, clock=self._clock)

    async def put(
        self,
        url: str,
        variant: str = "",
        *,
        etag: str | None,
        last_modified: str | None,
        status_code: int,
        content_type: str | None,
        body: bytes,
        ttl_s: int,
    ) -> None:
        """Store one response under ``(url, variant)`` with a ``ttl_s`` lifetime."""
        conn = await self._res.ensure()
        await cache_put(
            conn,
            url,
            variant,
            etag=etag,
            last_modified=last_modified,
            status_code=status_code,
            content_type=content_type,
            body=body,
            ttl_s=ttl_s,
            clock=self._clock,
        )

    async def close(self) -> None:
        """Close the underlying connection (idempotent)."""
        await self._res.close()

    async def __aenter__(self) -> Self:
        """Enter the context, opening the connection eagerly."""
        await self._res.ensure()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Exit the context, closing the connection."""
        await self.close()


__all__ = (
    "CacheRow",
    "HttpCache",
    "apply_schema",
    "cache_get",
    "cache_put",
    "conditional_headers",
)
