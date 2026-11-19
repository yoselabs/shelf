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
surfaces them (plus a manual :meth:`evict_expired`); the table, expiry and clock are
:class:`any_ttl_cache.TtlTable`'s, the key and the :class:`~anyllm.Completion` shape are this module's.

Connection-agnostic: the caller injects an open :class:`aiosqlite.Connection`
(e.g. from ``sqlite-resource``) — the cache owns its table, never the connection
lifecycle, so it can share one sqlite file with other tables.
"""

from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING

from any_ttl_cache import TtlTable
from anyllm import Completion

if TYPE_CHECKING:
    from collections.abc import Callable

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


class LlmCache:
    """An async sqlite-backed TTL cache over ``(key, model) -> Completion``.

    Construction is cheap — no I/O until first use. The table is created lazily
    and idempotently on the first ``get``/``put``.
    """

    def __init__(self, conn: aiosqlite.Connection, *, ttl_s: int = 900, clock: Callable[[], float] = time.time) -> None:
        """Configure the cache over an already-open connection.

        Args:
            conn: An open :class:`aiosqlite.Connection`. The cache owns its
                ``llm_cache`` table only, never the connection lifecycle.
            ttl_s: Seconds an entry stays fresh (clamped to ``>= 0``). ``0`` means
                every entry is born expired — useful for disabling reuse in tests.
            clock: Seconds since the epoch; inject a fake to step time in tests.
        """
        self._conn = conn
        self._ttl_s = max(0, ttl_s)
        self._table = TtlTable(
            name="llm_cache",
            keys=("cache_key", "model_id"),
            values=("text", "prompt_tokens", "completion_tokens", "cost_usd", "latency_ms"),
            stamped="cached_at",
            schema=_SCHEMA + _INDEX,
            clock=clock,
        )
        self._schema_ready = False

    @property
    def ttl_s(self) -> int:
        """The configured freshness window, in seconds."""
        return self._ttl_s

    async def ensure_schema(self) -> None:
        """Create the table + index if missing. Idempotent."""
        if self._schema_ready:
            return
        await self._table.ensure(self._conn)
        self._schema_ready = True

    async def get(self, *, key: str, model: str) -> Completion | None:
        """Return the cached completion for ``(key, model)`` if fresh, else ``None``.

        An expired row is deleted lazily on the read that surfaces it (along with
        any other expired rows). The returned :class:`~anyllm.Completion` carries
        the *original* cost/tokens/latency — the caller decides how to account for
        a hit (e.g. zero the cost, stash the original).
        """
        await self.ensure_schema()
        entry = await self._table.get(self._conn, (key, model))
        if entry is None:
            return None
        text, prompt_tokens, completion_tokens, cost_usd, latency_ms = entry.values
        return Completion(
            text=str(text),
            model=model,
            prompt_tokens=int(prompt_tokens),
            completion_tokens=int(completion_tokens),
            cost_usd=float(cost_usd),
            latency_ms=int(latency_ms),
        )

    async def put(self, *, key: str, model: str, completion: Completion) -> None:
        """Insert or replace the entry for ``(key, model)``. ``expires_at = now + ttl_s``.

        Only the accounting fields of ``completion`` are stored (``text``,
        token counts, ``cost_usd``, ``latency_ms``); ``raw`` is provider-specific
        debug data and is not persisted.
        """
        await self.ensure_schema()
        await self._table.put(
            self._conn,
            (key, model),
            (completion.text, completion.prompt_tokens, completion.completion_tokens, completion.cost_usd, completion.latency_ms),
            ttl_s=self._ttl_s,
        )

    async def evict_expired(self) -> int:
        """Delete all expired rows now. Returns the number removed."""
        await self.ensure_schema()
        return await self._table.evict_expired(self._conn)

    async def size(self) -> int:
        """Return the current row count (does not evict first)."""
        await self.ensure_schema()
        return await self._table.count(self._conn)


__all__ = [
    "LlmCache",
    "hash_text",
    "make_key",
]
