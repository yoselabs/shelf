"""A persistent embedding cache: one vector per ``(model_id, text)``, in its own SQLite file.

An index of vectors is derived data a host rebuilds — after damage, after a schema or
tokenizer change. The vectors themselves rarely change: the same text under the same
model embeds to the same vector. Keeping them in a file the rebuild does not touch turns
a re-embed of the whole corpus into a lookup.

The key is the model id and the sha256 of the exact text embedded (prefix included), so
a model swap or a changed prefix is a miss, never a stale hit. Bounded two ways: a row
cap evicts the least recently used rows on write, and :meth:`EmbeddingCache.prune` drops
the rows a full pass did not use (``unused_since`` = the pass's start).

Stdlib ``sqlite3`` only; safe to share between threads (one connection behind a lock).
"""

from __future__ import annotations

import hashlib
import sqlite3
import struct
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS embedding_cache(model_id TEXT NOT NULL, text_hash BLOB NOT NULL, "
    "dim INTEGER NOT NULL, vector BLOB NOT NULL, last_used REAL NOT NULL, PRIMARY KEY (model_id, text_hash)) WITHOUT ROWID",
    "CREATE INDEX IF NOT EXISTS embedding_cache_lru ON embedding_cache(last_used)",
)

#: Default row cap: about 2 GB of 1024-d float32 vectors.
MAX_ROWS = 500_000


def _hash(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def _pack(vector: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _unpack(blob: bytes, dim: int) -> list[float]:
    return list(struct.unpack(f"<{dim}f", blob))


class EmbeddingCache:
    """Vectors by ``(model_id, sha256(text))``, LRU-bounded, in one SQLite file."""

    def __init__(self, path: str | Path, *, max_rows: int = MAX_ROWS, clock: Callable[[], float] = time.time) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        for ddl in _SCHEMA:
            self._conn.execute(ddl)
        self._lock = threading.Lock()
        self._max_rows = max_rows
        self._clock = clock
        self.path = Path(path) if str(path) != ":memory:" else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __len__(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT count(*) FROM embedding_cache").fetchone()
        return int(row[0])

    def get(self, model_id: str, texts: Sequence[str]) -> list[list[float] | None]:
        """Each text's cached vector under ``model_id``, or ``None``; a hit is marked used now."""
        hashes = [_hash(t) for t in texts]
        found: dict[bytes, list[float]] = {}
        with self._lock:
            for h in set(hashes):
                row = self._conn.execute(
                    "SELECT dim, vector FROM embedding_cache WHERE model_id = ? AND text_hash = ?", (model_id, h)
                ).fetchone()
                if row is not None:
                    found[h] = _unpack(row[1], int(row[0]))
            if found:
                now = self._clock()
                self._conn.executemany(
                    "UPDATE embedding_cache SET last_used = ? WHERE model_id = ? AND text_hash = ?", [(now, model_id, h) for h in found]
                )
        return [found.get(h) for h in hashes]

    def put(self, model_id: str, texts: Sequence[str], vectors: Sequence[Sequence[float]]) -> None:
        """Store ``vectors`` (one per text), then evict the least recently used rows past the cap."""
        if len(texts) != len(vectors):
            msg = f"{len(texts)} texts but {len(vectors)} vectors"
            raise ValueError(msg)
        if not texts:
            return
        now = self._clock()
        rows = [(model_id, _hash(t), len(v), _pack(v), now) for t, v in zip(texts, vectors, strict=True)]
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                self._conn.executemany("INSERT OR REPLACE INTO embedding_cache VALUES (?, ?, ?, ?, ?)", rows)
                over = int(self._conn.execute("SELECT count(*) FROM embedding_cache").fetchone()[0]) - self._max_rows
                if over > 0:
                    self._conn.execute(
                        "DELETE FROM embedding_cache WHERE (model_id, text_hash) IN "
                        "(SELECT model_id, text_hash FROM embedding_cache ORDER BY last_used LIMIT ?)",
                        (over,),
                    )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def embed(self, model_id: str, texts: Sequence[str], compute: Callable[[list[str]], list[list[float]]]) -> list[list[float]]:
        """Each text's vector: cached where it is, ``compute``d (and stored) where it is not."""
        cached = self.get(model_id, texts)
        missing = list(dict.fromkeys(t for t, v in zip(texts, cached, strict=True) if v is None))
        if missing:
            computed = dict(zip(missing, compute(missing), strict=True))
            self.put(model_id, missing, [computed[t] for t in missing])
            return [v if v is not None else computed[t] for t, v in zip(texts, cached, strict=True)]
        return [v for v in cached if v is not None]

    def prune(self, *, unused_since: float, model_id: str | None = None) -> int:
        """Drop the rows not used since ``unused_since`` (optionally of one model); returns how many."""
        with self._lock:
            if model_id is None:
                cur = self._conn.execute("DELETE FROM embedding_cache WHERE last_used < ?", (unused_since,))
            else:
                cur = self._conn.execute("DELETE FROM embedding_cache WHERE model_id = ? AND last_used < ?", (model_id, unused_since))
            return cur.rowcount


__all__ = ["MAX_ROWS", "EmbeddingCache"]
