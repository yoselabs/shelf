"""Golden: a database written by http-cache 0.1.0 (before the TTL table moved to any-ttl-cache).

`fixtures/old_http_cache.sqlite` was generated with the OLD code and the clock pinned to
1_700_000_000: two fresh rows (ttl 900, one body of 500 bytes) and one born expired
(ttl -1). The new code must read it and, writing the same rows, must produce the same schema
and the same table contents (bodies compared decompressed).
"""

from __future__ import annotations

import gzip
import hashlib
import shutil
import sqlite3
from pathlib import Path

import pytest
from http_cache import CacheRow, HttpCache, conditional_headers

_FIXTURE = Path(__file__).parent / "fixtures" / "old_http_cache.sqlite"
_WRITTEN = 1_700_000_000


@pytest.fixture
def old_db(tmp_path: Path) -> Path:
    copy = tmp_path / "old.sqlite"
    shutil.copy(_FIXTURE, copy)
    return copy


async def test_new_code_reads_an_old_database(old_db: Path) -> None:
    async with HttpCache(old_db, clock=lambda: _WRITTEN + 100) as cache:
        row = await cache.get("https://x/page")
        other = await cache.get("https://x/page", "profileA")
    assert row == CacheRow(
        url="https://x/page",
        variant="",
        etag='"abc"',
        last_modified="Wed, 08 Jul 2026 00:00:00 GMT",
        fetched_at=_WRITTEN,
        expires_at=_WRITTEN + 900,
        status_code=200,
        content_type="text/html",
        content_hash=hashlib.sha256(b"<html>hi</html>").hexdigest(),
        body=b"<html>hi</html>",
    )
    assert conditional_headers(row) == {"If-None-Match": '"abc"', "If-Modified-Since": "Wed, 08 Jul 2026 00:00:00 GMT"}
    assert other is not None
    assert (other.status_code, other.etag, other.body) == (203, None, b"A" * 500)


async def test_an_old_expired_row_is_a_miss(old_db: Path) -> None:
    async with HttpCache(old_db, clock=lambda: _WRITTEN + 100) as cache:
        assert await cache.get("https://x/old") is None


async def test_old_rows_expire_by_their_stored_expires_at(old_db: Path) -> None:
    async with HttpCache(old_db, clock=lambda: _WRITTEN + 900) as cache:
        assert await cache.get("https://x/page") is None


def _dump(path: Path) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    with sqlite3.connect(path) as conn:
        schema = conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY name").fetchall()
        rows = conn.execute("SELECT * FROM cache ORDER BY url, variant").fetchall()
    # The gzip header carries the wall-clock second of compression, which no clock here controls;
    # the compressed payload is compared through what it decompresses to.
    return schema, [(*r[:9], gzip.decompress(r[9])) for r in rows]


async def test_new_code_writes_the_same_schema_and_rows_as_the_old(old_db: Path, tmp_path: Path) -> None:
    fresh = tmp_path / "fresh.sqlite"
    async with HttpCache(fresh, clock=lambda: _WRITTEN) as cache:
        await cache.put(
            "https://x/page",
            etag='"abc"',
            last_modified="Wed, 08 Jul 2026 00:00:00 GMT",
            status_code=200,
            content_type="text/html",
            body=b"<html>hi</html>",
            ttl_s=900,
        )
        await cache.put(
            "https://x/page", "profileA", etag=None, last_modified=None, status_code=203, content_type=None, body=b"A" * 500, ttl_s=900
        )
        await cache.put("https://x/old", etag=None, last_modified=None, status_code=200, content_type=None, body=b"old", ttl_s=-1)
    new_schema, new_rows = _dump(fresh)
    old_schema, old_rows = _dump(old_db)
    assert new_schema == old_schema
    assert new_rows == old_rows
