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
import hashlib
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from sqlite_resource import SqliteResource

if TYPE_CHECKING:
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
    await conn.execute(_SCHEMA)
    await conn.execute(_INDEX)


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


async def cache_get(conn: aiosqlite.Connection, url: str, variant: str = "") -> CacheRow | None:
    """Return a non-expired row for ``(url, variant)``, or ``None``."""
    async with conn.execute(
        "SELECT url, variant, etag, last_modified, fetched_at, expires_at, "
        "status_code, content_type, content_hash, body FROM cache "
        "WHERE url = ? AND variant = ? AND expires_at > ?",
        (url, variant, int(time.time())),
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return None
    return CacheRow(
        url=row[0],
        variant=row[1],
        etag=row[2],
        last_modified=row[3],
        fetched_at=row[4],
        expires_at=row[5],
        status_code=row[6],
        content_type=row[7],
        content_hash=row[8],
        body=gzip.decompress(row[9]),
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
) -> None:
    """Insert or replace one row. The caller decides *whether* to cache (gate first)."""
    now = int(time.time())
    content_hash = hashlib.sha256(body).hexdigest()
    compressed = gzip.compress(body)
    await conn.execute(
        "INSERT OR REPLACE INTO cache "
        "(url, variant, etag, last_modified, fetched_at, expires_at, "
        "status_code, content_type, content_hash, body) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (url, variant, etag, last_modified, now, now + ttl_s, status_code, content_type, content_hash, compressed),
    )
    await conn.commit()


class HttpCache:
    """A conditional-GET HTTP cache over one sqlite database.

    Thin policy-free store: :meth:`get` returns a live row (or ``None``), :meth:`put`
    writes one. Composes :class:`sqlite_resource.SqliteResource` for the connection
    lifecycle and applies the cache schema on open.
    """

    def __init__(self, db_path: Path) -> None:
        """Bind the cache to ``db_path`` (opened lazily on first use)."""
        self._res = SqliteResource(db_path, on_open=apply_schema)

    async def get(self, url: str, variant: str = "") -> CacheRow | None:
        """Return the non-expired cached response for ``(url, variant)``, or ``None``."""
        conn = await self._res.ensure()
        return await cache_get(conn, url, variant)

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
