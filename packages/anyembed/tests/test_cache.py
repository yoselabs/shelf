"""EmbeddingCache — keyed by model and exact text, LRU-capped, pruned of what a pass left unused."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from anyembed import EmbeddingCache

if TYPE_CHECKING:
    from pathlib import Path


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
