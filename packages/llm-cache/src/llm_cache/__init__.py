"""A sqlite-backed TTL cache for LLM completions, keyed on ``(key, model)``.

Stop caring about the sqlite plumbing of "have I already asked this exact thing
of this exact model?". :class:`LlmCache` stores and returns
:class:`anyllm.Completion` — the same currency the provider hands back — so a hit
is a drop-in for a call: the token counts, cost, and latency of the original
completion ride along, and the caller decides how to account for the (free) hit.

The cache is deliberately *policy-free*: it does not know what a "prompt" is, only
an opaque ``key`` string the caller computes (via :func:`make_key`) from whatever
determines answer identity — content, question, template, system prompt. Different
``model`` is always a distinct slot, so a model swap never reads a stale answer.
Entries self-expire after ``ttl_s`` and are evicted lazily on the read that
surfaces them (plus a manual :meth:`evict_expired`).

Connection-agnostic: the caller injects an open :class:`aiosqlite.Connection`
(e.g. from ``sqlite-resource``) — the cache owns its table, never the connection
lifecycle, so it can share one sqlite file with other tables.
"""

from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING

from anyllm import Completion

if TYPE_CHECKING:
    import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key         TEXT NOT NULL,
    model_id          TEXT NOT NULL,
    text              TEXT NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd          REAL NOT NULL DEFAULT 0.0,
    latency_ms        INTEGER NOT NULL DEFAULT 0,
    cached_at         INTEGER NOT NULL,
    expires_at        INTEGER NOT NULL,
    PRIMARY KEY (cache_key, model_id)
);
"""
_INDEX = "CREATE INDEX IF NOT EXISTS llm_cache_expires ON llm_cache(expires_at);"


def hash_text(text: str) -> str:
    """Return the stable sha256 hex digest of ``text``'s UTF-8 bytes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_key(*parts: str) -> str:
    """Build a cache key from ``parts`` by hashing each and joining with ``:``.

    Order matters — ``make_key(a, b)`` and ``make_key(b, a)`` differ. Pass the
    factors that determine answer identity (e.g. content, question, template).
    """
    return ":".join(hash_text(p) for p in parts)


def _now() -> int:
    return int(time.time())


class LlmCache:
    """An async sqlite-backed TTL cache over ``(key, model) -> Completion``.

    Construction is cheap — no I/O until first use. The table is created lazily
    and idempotently on the first ``get``/``put``.
    """

    def __init__(self, conn: aiosqlite.Connection, *, ttl_s: int = 900) -> None:
        """Configure the cache over an already-open connection.

        Args:
            conn: An open :class:`aiosqlite.Connection`. The cache owns its
                ``llm_cache`` table only, never the connection lifecycle.
            ttl_s: Seconds an entry stays fresh (clamped to ``>= 0``). ``0`` means
                every entry is born expired — useful for disabling reuse in tests.
        """
        self._conn = conn
        self._ttl_s = max(0, int(ttl_s))
        self._schema_ready = False

    @property
    def ttl_s(self) -> int:
        """The configured freshness window, in seconds."""
        return self._ttl_s

    async def ensure_schema(self) -> None:
        """Create the table + index if missing. Idempotent."""
        if self._schema_ready:
            return
        await self._conn.executescript(_SCHEMA + _INDEX)
        await self._conn.commit()
        self._schema_ready = True

    async def get(self, *, key: str, model: str) -> Completion | None:
        """Return the cached completion for ``(key, model)`` if fresh, else ``None``.

        An expired row is deleted lazily on the read that surfaces it (along with
        any other expired rows). The returned :class:`~anyllm.Completion` carries
        the *original* cost/tokens/latency — the caller decides how to account for
        a hit (e.g. zero the cost, stash the original).
        """
        await self.ensure_schema()
        now = _now()
        cursor = await self._conn.execute(
            "SELECT text, prompt_tokens, completion_tokens, cost_usd, latency_ms, expires_at "
            "FROM llm_cache WHERE cache_key=? AND model_id=? LIMIT 1",
            (key, model),
        )
        record = await cursor.fetchone()
        await cursor.close()
        if record is None:
            return None
        if int(record[5]) <= now:
            # Lazy eviction — also drops any other expired rows along the way.
            await self._evict_expired(now)
            return None
        return Completion(
            text=str(record[0]),
            model=model,
            prompt_tokens=int(record[1]),
            completion_tokens=int(record[2]),
            cost_usd=float(record[3]),
            latency_ms=int(record[4]),
        )

    async def put(self, *, key: str, model: str, completion: Completion) -> None:
        """Insert or replace the entry for ``(key, model)``. ``expires_at = now + ttl_s``.

        Only the accounting fields of ``completion`` are stored (``text``,
        token counts, ``cost_usd``, ``latency_ms``); ``raw`` is provider-specific
        debug data and is not persisted.
        """
        await self.ensure_schema()
        now = _now()
        await self._conn.execute(
            "INSERT OR REPLACE INTO llm_cache "
            "(cache_key, model_id, text, prompt_tokens, completion_tokens, cost_usd, latency_ms, cached_at, expires_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                key,
                model,
                completion.text,
                completion.prompt_tokens,
                completion.completion_tokens,
                completion.cost_usd,
                completion.latency_ms,
                now,
                now + self._ttl_s,
            ),
        )
        await self._conn.commit()

    async def evict_expired(self) -> int:
        """Delete all expired rows now. Returns the number removed."""
        return await self._evict_expired(_now())

    async def _evict_expired(self, now: int) -> int:
        cursor = await self._conn.execute("DELETE FROM llm_cache WHERE expires_at <= ?", (now,))
        await self._conn.commit()
        return cursor.rowcount or 0

    async def size(self) -> int:
        """Return the current row count (does not evict first)."""
        await self.ensure_schema()
        cursor = await self._conn.execute("SELECT COUNT(*) FROM llm_cache")
        record = await cursor.fetchone()
        await cursor.close()
        return int(record[0]) if record else 0


__all__ = [
    "LlmCache",
    "hash_text",
    "make_key",
]
