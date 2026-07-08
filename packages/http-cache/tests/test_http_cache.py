"""HttpCache: round-trip, variant keying, TTL expiry, conditional headers."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest
from http_cache import CacheRow, HttpCache, conditional_headers

if TYPE_CHECKING:
    from pathlib import Path


async def _store(
    cache: HttpCache,
    url: str,
    variant: str = "",
    *,
    body: bytes = b"<html>hi</html>",
    ttl_s: int = 900,
) -> None:
    await cache.put(
        url,
        variant,
        etag='"abc"',
        last_modified="Wed, 08 Jul 2026 00:00:00 GMT",
        status_code=200,
        content_type="text/html",
        body=body,
        ttl_s=ttl_s,
    )


async def test_put_then_get_round_trip(tmp_path: Path) -> None:
    cache = HttpCache(tmp_path / "c.sqlite")
    async with cache:
        await _store(cache, "https://x/")
        row = await cache.get("https://x/")
    assert row is not None
    assert row.body == b"<html>hi</html>"
    assert row.etag == '"abc"'
    assert row.content_hash  # sha256 populated


async def test_miss_returns_none(tmp_path: Path) -> None:
    cache = HttpCache(tmp_path / "c.sqlite")
    async with cache:
        assert await cache.get("https://absent/") is None


async def test_variant_isolation(tmp_path: Path) -> None:
    cache = HttpCache(tmp_path / "c.sqlite")
    async with cache:
        await _store(cache, "https://x/", "profileA", body=b"A")
        await _store(cache, "https://x/", "profileB", body=b"B")
        a = await cache.get("https://x/", "profileA")
        b = await cache.get("https://x/", "profileB")
    assert a is not None
    assert b is not None
    assert (a.body, b.body) == (b"A", b"B")


async def test_expired_row_is_not_returned(tmp_path: Path) -> None:
    cache = HttpCache(tmp_path / "c.sqlite")
    async with cache:
        await _store(cache, "https://x/", ttl_s=-1)
        assert await cache.get("https://x/") is None


async def test_put_replaces_existing(tmp_path: Path) -> None:
    cache = HttpCache(tmp_path / "c.sqlite")
    async with cache:
        await _store(cache, "https://x/", body=b"old")
        await _store(cache, "https://x/", body=b"new")
        row = await cache.get("https://x/")
    assert row is not None
    assert row.body == b"new"


def test_conditional_headers_from_row() -> None:
    row = CacheRow(
        url="https://x/",
        variant="",
        etag='"abc"',
        last_modified="Wed, 08 Jul 2026 00:00:00 GMT",
        fetched_at=int(time.time()),
        expires_at=int(time.time()) + 900,
        status_code=200,
        content_type="text/html",
        content_hash="deadbeef",
        body=b"x",
    )
    headers = conditional_headers(row)
    assert headers == {
        "If-None-Match": '"abc"',
        "If-Modified-Since": "Wed, 08 Jul 2026 00:00:00 GMT",
    }


def test_conditional_headers_none_and_empty() -> None:
    assert conditional_headers(None) == {}
    bare = CacheRow(
        url="https://x/",
        variant="",
        etag=None,
        last_modified=None,
        fetched_at=0,
        expires_at=0,
        status_code=200,
        content_type=None,
        content_hash="h",
        body=b"",
    )
    assert conditional_headers(bare) == {}


@pytest.mark.parametrize("variant", ["", "p1"])
async def test_free_functions_via_resource(tmp_path: Path, variant: str) -> None:
    cache = HttpCache(tmp_path / "c.sqlite")
    async with cache:
        await _store(cache, "https://x/", variant)
        row = await cache.get("https://x/", variant)
    assert row is not None
    assert row.variant == variant
