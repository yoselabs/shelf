"""A written row's content hash stays the full sha256 hex of the raw body (stored bytes unchanged)."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from http_cache import HttpCache

if TYPE_CHECKING:
    from pathlib import Path


async def test_put_stores_plain_sha256_of_the_body(tmp_path: Path) -> None:
    body = "<html>héllo</html>".encode() + bytes(range(256))
    async with HttpCache(tmp_path / "c.sqlite") as cache:
        await cache.put("https://x/", "", etag=None, last_modified=None, status_code=200, content_type=None, body=body, ttl_s=900)
        row = await cache.get("https://x/")
    assert row is not None
    assert row.content_hash == hashlib.sha256(body).hexdigest()
    assert len(row.content_hash) == 64
