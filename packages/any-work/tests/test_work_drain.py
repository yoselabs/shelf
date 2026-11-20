"""drain: claim, run, finish by result, exit when idle. Time is the test's clock; the injected sleep moves it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from any_work import Claimed, ClassifiedError, Failure, Item, Kind, Status, Work, drain

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from any_work.testing import ManualClock


async def run(work: Work, clock: ManualClock, handler: Callable[[Claimed], Awaitable[None]], concurrency: int = 1) -> None:
    await drain(work, handler, concurrency=concurrency, idle_exit_s=30, poll_s=5, sleep=clock.sleep, clock=clock)


async def test_an_empty_table_exits_after_the_idle_spell(work: Work, clock: ManualClock) -> None:
    async def never(_: Claimed) -> None:
        raise AssertionError

    start = clock.now
    await run(work, clock, never)
    assert clock.now - start == 30  # six polls of 5 s, then out


async def test_ok_permanent_and_unclassified_results_finish_their_rows(work: Work, clock: ManualClock) -> None:
    work.add([Item("ok"), Item("gone"), Item("odd")])
    seen: list[str] = []

    async def handler(c: Claimed) -> None:
        seen.append(c.key)
        if c.key == "gone":
            raise ClassifiedError(Failure(Kind.PERMANENT, "removed"))
        if c.key == "odd":
            message = "unexpected shape"
            raise ValueError(message)

    await run(work, clock, handler)
    assert sorted(seen[:3]) == ["gone", "odd", "ok"]
    assert seen.count("odd") == 3  # retried to max_attempts, never stopped early as permanent
    p = work.progress()
    assert (p.done, p.by_status[Status.PERMANENT], p.by_status[Status.QUARANTINED]) == (1, 1, 1)


async def test_an_always_failing_unclassified_item_is_retried_then_quarantined_never_permanent(work: Work, clock: ManualClock) -> None:
    work.add([Item("odd")])
    calls = 0

    async def handler(_: Claimed) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError

    await run(work, clock, handler)
    p = work.progress()
    assert calls == 3  # max_attempts
    assert p.by_status[Status.QUARANTINED] == 1
    assert p.by_status[Status.PERMANENT] == 0


async def test_a_handler_that_finished_its_own_item_is_not_finished_twice(work: Work, clock: ManualClock) -> None:
    work.add([Item("a")])

    async def handler(c: Claimed) -> None:
        c.finish(Failure(Kind.PERMANENT, "mine"))

    await run(work, clock, handler)
    assert work.progress().by_status[Status.PERMANENT] == 1


async def test_workers_share_items_and_run_each_once(work: Work, clock: ManualClock) -> None:
    work.add([Item(f"k{i}") for i in range(7)])
    ran: list[str] = []

    async def handler(c: Claimed) -> None:
        await clock.sleep(0)
        ran.append(c.key)

    await run(work, clock, handler, 3)
    assert sorted(ran) == [f"k{i}" for i in range(7)]
    assert work.progress().done == 7
