from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from any_pipeline import Failed, Limit, MemoryStore, Ok, Persistent, Stage, blocking, gather, run, run_one

L = Limit(calls=4, seconds=5.0, tries=1)


@dataclass(frozen=True, slots=True)
class Doc:
    name: str
    size: int


def key(d: Doc) -> str:
    return d.name


async def size(d: Doc) -> int:
    return d.size


async def double(n: int) -> int:
    return n * 2


async def test_a_chain_returns_values_in_item_order() -> None:
    report = await run(Stage("size", size, L) >> Stage("double", double, L), [Doc("a", 1), Doc("b", 5)], key=key, workers=2)
    assert report.outcomes == (Ok("a", 2), Ok("b", 10))
    assert [r.stage for r in report.records if r.key == "a"] == ["size", "double"]


async def test_one_failing_item_is_recorded_and_never_stops_the_others() -> None:
    async def picky(d: Doc) -> int:
        if d.size < 0:
            message = "negative size"
            raise ValueError(message)
        return d.size

    report = await run(Stage("picky", picky, L), [Doc("a", 1), Doc("bad", -1), Doc("c", 3)], key=key, workers=1)
    assert report.outcomes == (Ok("a", 1), Failed("bad", "picky", "ValueError: negative size"), Ok("c", 3))
    assert [f.key for f in report.failed] == ["bad"] and [o.key for o in report.done] == ["a", "c"]


async def test_retries_stop_at_the_limit() -> None:
    calls: list[int] = []

    async def flaky(d: Doc) -> int:
        calls.append(1)
        if len(calls) < 3:
            message = "not yet"
            raise RuntimeError(message)
        return d.size

    ok = await run(Stage("flaky", flaky, Limit(1, 5.0, tries=3)), [Doc("a", 1)], key=key, workers=1)
    assert ok.outcomes == (Ok("a", 1),) and ok.records[0].tries == 3
    calls.clear()

    async def never(d: Doc) -> int:
        calls.append(1)
        message = "always"
        raise RuntimeError(message)

    bad = await run(Stage("never", never, Limit(1, 5.0, tries=2)), [Doc("a", 1)], key=key, workers=1)
    assert len(calls) == 2 and isinstance(bad.outcomes[0], Failed) and bad.records[0].ok is False


async def test_a_stage_that_awaits_is_cancelled_at_its_time_limit() -> None:
    async def hang(d: Doc) -> int:
        await asyncio.sleep(30)
        return d.size

    report = await run(Stage("hang", hang, Limit(1, 0.05, 1)), [Doc("a", 1)], key=key, workers=1)
    failed = report.outcomes[0]
    assert isinstance(failed, Failed) and "TimeoutError" in failed.why


async def test_gather_runs_branches_at_the_same_time_and_a_failed_branch_stops_its_sibling() -> None:
    both_started = asyncio.Barrier(2)

    async def left(d: Doc) -> int:
        await asyncio.wait_for(both_started.wait(), 2)
        return 1

    async def right(d: Doc) -> str:
        await asyncio.wait_for(both_started.wait(), 2)
        return "r"

    report = await run(gather(Stage("left", left, L), Stage("right", right, L)), [Doc("a", 1)], key=key, workers=1)
    assert report.outcomes == (Ok("a", (1, "r")),)

    stopped: list[str] = []

    async def slow(d: Doc) -> int:
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            stopped.append("slow")
            raise
        return 0

    async def boom(d: Doc) -> int:
        message = "boom"
        raise RuntimeError(message)

    bad = await run(gather(Stage("slow", slow, L), Stage("boom", boom, L)), [Doc("a", 1)], key=key, workers=1)
    assert isinstance(bad.outcomes[0], Failed) and bad.outcomes[0].stage == "boom"
    assert stopped == ["slow"]


async def test_a_stage_never_has_more_calls_in_flight_than_its_limit() -> None:
    inside = most = 0

    async def work(d: Doc) -> int:
        nonlocal inside, most
        inside += 1
        most = max(most, inside)
        await asyncio.sleep(0.01)
        inside -= 1
        return d.size

    docs = [Doc(str(i), i) for i in range(8)]
    await run(Stage("work", work, Limit(calls=2, seconds=5.0, tries=1)), docs, key=key, workers=8)
    assert most == 2


async def test_workers_bound_how_many_items_are_in_flight() -> None:
    inside = most = 0

    async def work(d: Doc) -> int:
        nonlocal inside, most
        inside += 1
        most = max(most, inside)
        await asyncio.sleep(0.01)
        inside -= 1
        return d.size

    await run(Stage("work", work, Limit(100, 5.0, 1)), [Doc(str(i), i) for i in range(6)], key=key, workers=3)
    assert most == 3


async def test_a_blocking_function_runs_off_the_loop() -> None:
    import threading  # noqa: PLC0415  only to name the thread

    main = threading.get_ident()

    def sync_size(d: Doc) -> int:
        return -1 if threading.get_ident() == main else d.size

    report = await run(Stage("sync", blocking(sync_size), L), [Doc("a", 7)], key=key, workers=1)
    assert report.outcomes == (Ok("a", 7),)


async def test_a_mutable_item_is_refused_before_anything_runs() -> None:
    called: list[int] = []

    async def noop(d: list[int]) -> int:
        called.append(1)
        return 0

    with pytest.raises(TypeError, match="frozen"):
        await run(Stage("noop", noop, L), [[1, 2]], key=str, workers=1)
    assert called == []


async def test_a_mutable_result_is_a_failure_of_that_stage() -> None:
    async def listy(d: Doc) -> list[int]:
        return [d.size]

    report = await run(Stage("listy", listy, L), [Doc("a", 1)], key=key, workers=1)
    failed = report.outcomes[0]
    assert isinstance(failed, Failed) and "frozen" in failed.why


async def test_a_persistent_stage_is_skipped_when_its_key_already_has_a_result() -> None:
    calls: list[str] = []

    async def costly(d: Doc) -> int:
        calls.append(d.name)
        return d.size

    store: MemoryStore[int] = MemoryStore()
    stage = Persistent("costly", costly, L, key=lambda d: f"{d.name}:{d.size}", store=store)
    first = await run(stage, [Doc("a", 1)], key=key, workers=1)
    second = await run(stage, [Doc("a", 1)], key=key, workers=1)
    assert calls == ["a"] and second.outcomes == first.outcomes
    assert [(r.skipped, r.tries) for r in second.records] == [(True, 0)]


async def test_workers_below_one_are_refused() -> None:
    with pytest.raises(ValueError, match="workers"):
        await run(Stage("size", size, L), [Doc("a", 1)], key=key, workers=0)


async def test_a_failure_keeps_the_original_exception_and_run_one_raises_it() -> None:
    async def boom(d: Doc) -> int:
        message = "too big"
        raise OverflowError(message)

    stage = Stage("boom", boom, L)
    report = await run(stage, [Doc("a", 1)], key=key, workers=1)
    failed = report.failed[0]
    assert isinstance(failed.cause, OverflowError) and failed == Failed("a", "boom", "OverflowError: too big")
    with pytest.raises(OverflowError, match="too big"):
        await run_one(stage, Doc("a", 1), key="a")
    assert await run_one(Stage("size", size, L), Doc("a", 4), key="a") == 4


async def test_a_tolerated_stage_returns_a_typed_fallback_and_the_record_still_shows_the_failure() -> None:
    async def boom(d: Doc) -> int:
        message = "no model"
        raise RuntimeError(message)

    stage = Stage("boom", boom, L).otherwise(lambda why: -1)
    report = await run(stage >> Stage("double", double, L), [Doc("a", 1)], key=key, workers=1)
    assert report.outcomes == (Ok("a", -2),)
    assert [(r.stage, r.ok) for r in report.records] == [("boom", False), ("double", True)]


async def test_two_items_with_one_key_are_refused() -> None:
    with pytest.raises(ValueError, match="key"):
        await run(Stage("size", size, L), [Doc("a", 1), Doc("a", 2)], key=key, workers=1)


def test_a_flow_prints_as_its_shape() -> None:
    flow = gather(Stage("i", size, L), Stage("j", size, L)) >> Stage("k", double2, L)
    assert str(flow) == "gather(i, j) >> k"


async def double2(p: tuple[int, int]) -> int:
    return p[0] + p[1]
