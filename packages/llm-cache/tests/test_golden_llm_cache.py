"""Golden: a database written by llm-cache 0.1.2 (before the TTL table moved to any-ttl-cache).

`fixtures/old_llm_cache.sqlite` was generated with the OLD code and the clock pinned to
1_700_000_000: two fresh rows (ttl 900), one born expired (ttl 0). The new code must read it
and, writing the same rows, must produce the same schema and the same table contents.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import aiosqlite
import pytest
from anyllm import Completion
from llm_cache import LlmCache

_FIXTURE = Path(__file__).parent / "fixtures" / "old_llm_cache.sqlite"
_WRITTEN = 1_700_000_000


@pytest.fixture
async def old_conn(tmp_path: Path):
    copy = tmp_path / "old.sqlite"
    shutil.copy(_FIXTURE, copy)
    async with aiosqlite.connect(copy) as conn:
        yield conn


async def test_new_code_reads_an_old_database(old_conn) -> None:
    cache = LlmCache(old_conn, ttl_s=900, clock=lambda: _WRITTEN + 100)
    hit = await cache.get(key="fresh", model="m1")
    assert hit == Completion(text="héllo", model="m1", prompt_tokens=11, completion_tokens=3, cost_usd=0.0125, latency_ms=210)
    other = await cache.get(key="fresh", model="m2")
    assert other is not None
    assert other.text == "other model"


async def test_an_old_expired_row_is_a_miss_and_is_evicted(old_conn) -> None:
    cache = LlmCache(old_conn, ttl_s=900, clock=lambda: _WRITTEN + 100)
    assert await cache.get(key="stale", model="m1") is None
    assert await cache.size() == 2


async def test_old_rows_expire_by_their_stored_expires_at(old_conn) -> None:
    cache = LlmCache(old_conn, ttl_s=900, clock=lambda: _WRITTEN + 900)
    assert await cache.get(key="fresh", model="m1") is None


async def _dump(conn: aiosqlite.Connection) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    async with conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY name") as cursor:
        schema = [tuple(r) for r in await cursor.fetchall()]
    async with conn.execute("SELECT * FROM llm_cache ORDER BY cache_key, model_id") as cursor:
        rows = [tuple(r) for r in await cursor.fetchall()]
    return schema, rows


async def test_new_code_writes_the_same_schema_and_rows_as_the_old(old_conn) -> None:
    async with aiosqlite.connect(":memory:") as fresh:
        cache = LlmCache(fresh, ttl_s=900, clock=lambda: _WRITTEN)
        await cache.put(
            key="fresh",
            model="m1",
            completion=Completion(text="héllo", model="m1", prompt_tokens=11, completion_tokens=3, cost_usd=0.0125, latency_ms=210),
        )
        await cache.put(
            key="fresh",
            model="m2",
            completion=Completion(text="other model", model="m2", prompt_tokens=1, completion_tokens=2, cost_usd=0.5, latency_ms=3),
        )
        await LlmCache(fresh, ttl_s=0, clock=lambda: _WRITTEN).put(
            key="stale",
            model="m1",
            completion=Completion(text="stale", model="m1", prompt_tokens=0, completion_tokens=0, cost_usd=0.0, latency_ms=0),
        )
        assert await _dump(fresh) == await _dump(old_conn)
