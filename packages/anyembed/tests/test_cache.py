"""EmbeddingCache — keyed by model and exact text, LRU-capped, pruned of what a pass left unused."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path

import pytest
from anyembed import EmbeddingCache


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class _Counting:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(t)), 0.5] for t in texts]


def test_a_second_pass_reads_the_vectors_back(tmp_path: Path) -> None:
    compute = _Counting()
    cache = EmbeddingCache(tmp_path / "cache.sqlite")
    first = cache.embed("m", ["aa", "bbb"], compute)
    cache.close()
    reopened = EmbeddingCache(tmp_path / "cache.sqlite")
    second = reopened.embed("m", ["bbb", "aa"], compute)
    assert first == [[2.0, 0.5], [3.0, 0.5]]
    assert second == [[3.0, 0.5], [2.0, 0.5]]
    assert compute.calls == [["aa", "bbb"]]


def test_another_model_or_another_text_is_a_miss() -> None:
    compute = _Counting()
    cache = EmbeddingCache(":memory:")
    cache.embed("m", ["aa"], compute)
    cache.embed("n", ["aa"], compute)
    cache.embed("m", ["aa "], compute)
    assert compute.calls == [["aa"], ["aa"], ["aa "]]


def test_only_the_misses_are_computed_and_a_repeat_once() -> None:
    compute = _Counting()
    cache = EmbeddingCache(":memory:")
    cache.embed("m", ["aa"], compute)
    out = cache.embed("m", ["aa", "c", "c"], compute)
    assert compute.calls == [["aa"], ["c"]]
    assert out == [[2.0, 0.5], [1.0, 0.5], [1.0, 0.5]]


def test_the_cap_evicts_the_least_recently_used() -> None:
    clock = _Clock()
    compute = _Counting()
    cache = EmbeddingCache(":memory:", max_rows=2, clock=clock)
    cache.embed("m", ["a"], compute)
    clock.now += 1
    cache.embed("m", ["b"], compute)
    clock.now += 1
    cache.get("m", ["a"])  # `a` is now the more recent
    clock.now += 1
    cache.embed("m", ["c"], compute)
    assert len(cache) == 2
    assert cache.get("m", ["a", "b", "c"])[1] is None


def test_prune_drops_what_a_pass_did_not_use() -> None:
    clock = _Clock()
    cache = EmbeddingCache(":memory:", clock=clock)
    cache.embed("m", ["old", "kept"], _Counting())
    clock.now += 10
    started = clock.now
    cache.embed("m", ["kept", "new"], _Counting())
    assert cache.prune(unused_since=started) == 1
    assert cache.get("m", ["old", "kept", "new"])[0] is None
    assert len(cache) == 2


def test_prune_of_one_model_leaves_the_others() -> None:
    clock = _Clock()
    cache = EmbeddingCache(":memory:", clock=clock)
    cache.embed("m", ["a"], _Counting())
    cache.embed("n", ["a"], _Counting())
    assert cache.prune(unused_since=clock.now + 1, model_id="m") == 1
    assert len(cache) == 1


def test_put_refuses_a_length_mismatch() -> None:
    with pytest.raises(ValueError, match="texts"):
        EmbeddingCache(":memory:").put("m", ["a"], [])


_FIXTURE = Path(__file__).parent / "fixtures" / "old_cache.sqlite"


def test_a_database_made_by_the_old_code_reads_back_and_keeps_its_layout(tmp_path: Path) -> None:
    # old_cache.sqlite was written by the pre-sidecar cache: raw sha256 digests as keys, this schema.
    path = tmp_path / "old.sqlite"
    shutil.copy(_FIXTURE, path)
    cache = EmbeddingCache(path)
    assert cache.get("model-a", ["hello", "héllo ☃", "absent"]) == [[1.0, 2.5], [0.25, -1.0], None]
    cache.put("model-a", ["new"], [[3.0, 4.0]])
    cache.close()
    con = sqlite3.connect(path)
    keys = {bytes(r[0]) for r in con.execute("SELECT text_hash FROM embedding_cache")}
    schema = [r[0] for r in con.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name")]
    con.close()
    assert keys == {hashlib.sha256(t.encode()).digest() for t in ("hello", "héllo ☃", "new")}
    assert schema == [
        (
            "CREATE TABLE embedding_cache(model_id TEXT NOT NULL, text_hash BLOB NOT NULL, "
            "dim INTEGER NOT NULL, vector BLOB NOT NULL, last_used REAL NOT NULL, PRIMARY KEY (model_id, text_hash)) WITHOUT ROWID"
        ),
        "CREATE INDEX embedding_cache_lru ON embedding_cache(last_used)",
    ]
