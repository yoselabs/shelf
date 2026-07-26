"""Acceptance suite for llm-cache — get/put/evict against in-memory sqlite.

Covers the round trip (Completion in, Completion out), model + key isolation,
TTL lazy eviction, and the manual evict/size accounting.
"""

from __future__ import annotations

import asyncio

import aiosqlite
import pytest
from anyllm import Completion
from llm_cache import LlmCache, hash_text, make_key


@pytest.fixture
async def conn():
    connection = await aiosqlite.connect(":memory:")
    try:
        yield connection
    finally:
        await connection.close()


def _completion(text: str, *, cost: float = 0.0005, model: str = "claude-haiku-4-5") -> Completion:
    return Completion(
        text=text,
        model=model,
        prompt_tokens=10,
        completion_tokens=2,
        cost_usd=cost,
        latency_ms=120,
    )


async def test_get_miss_returns_none(conn) -> None:
    cache = LlmCache(conn, ttl_s=900)
    assert await cache.get(key="nope", model="m") is None


async def test_put_then_get_round_trip(conn) -> None:
    cache = LlmCache(conn, ttl_s=900)
    key = make_key("hello", "what?")
    await cache.put(key=key, model="claude-haiku-4-5", completion=_completion("world"))

    hit = await cache.get(key=key, model="claude-haiku-4-5")
    assert hit is not None
    assert hit.text == "world"
    assert hit.model == "claude-haiku-4-5"
    assert hit.prompt_tokens == 10
    assert hit.completion_tokens == 2
    assert hit.cost_usd == pytest.approx(0.0005)
    assert hit.latency_ms == 120


async def test_keys_isolate_by_model(conn) -> None:
    """Same key, different model → independent slots (a swap never reads stale)."""
    cache = LlmCache(conn, ttl_s=900)
    key = make_key("hi", "q")
    await cache.put(key=key, model="haiku", completion=_completion("haiku says hi", model="haiku"))

    assert await cache.get(key=key, model="sonnet") is None
    hit = await cache.get(key=key, model="haiku")
    assert hit is not None
    assert hit.text == "haiku says hi"


async def test_make_key_is_order_sensitive_and_distinct() -> None:
    assert make_key("a", "b") != make_key("b", "a")
    assert make_key("a", "b") != make_key("a", "c")
    # Deterministic + composed of the part digests joined by ':'.
    assert make_key("a", "b") == f"{hash_text('a')}:{hash_text('b')}"


async def test_expired_row_is_evicted_on_read(conn) -> None:
    """ttl_s=0 → every put is born expired; the next get evicts it."""
    cache = LlmCache(conn, ttl_s=0)
    await cache.put(key="k", model="m", completion=_completion("stale"))
    await asyncio.sleep(1.1)  # push the clock past expires_at
    assert await cache.get(key="k", model="m") is None
    assert await cache.size() == 0


async def test_evict_expired_returns_count(conn) -> None:
    cache = LlmCache(conn, ttl_s=0)
    for i in range(3):
        await cache.put(key=f"k{i}", model="m", completion=_completion(str(i)))
    await asyncio.sleep(1.1)
    assert await cache.evict_expired() == 3
    assert await cache.size() == 0


async def test_put_replaces_existing_entry(conn) -> None:
    cache = LlmCache(conn, ttl_s=900)
    await cache.put(key="k", model="m", completion=_completion("first"))
    await cache.put(key="k", model="m", completion=_completion("second"))
    hit = await cache.get(key="k", model="m")
    assert hit is not None
    assert hit.text == "second"
    assert await cache.size() == 1
