"""enqueue and bump: a feeder's evidence, and work added from outside is claimable at once."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from any_work import Enqueued, Failure, Item, Kind, Work

if TYPE_CHECKING:
    from pathlib import Path

    from any_work.testing import ManualClock


def claim_order(work: Work) -> list[str]:
    """Keys in the order claim hands them out; every claim stays held so the next one moves on."""
    got = []
    while (c := work.claim()) is not None:
        got.append(c)
    keys = [c.key for c in got]
    for c in got:
        c.release()
    return keys


def finish(work: Work, ok: bool = True) -> str:
    c = work.claim()
    assert c is not None
    c.finish(None if ok else Failure(Kind.PERMANENT, "gone"))
    return c.key


def test_enqueue_counts_new_existing_and_bumped(work: Work) -> None:
    assert work.enqueue([Item("a", priority=1), Item("b", priority=1)]) == Enqueued(new=2, existing=0, bumped=0, states={"pending": 2})
    got = work.enqueue([Item("a", priority=0), Item("b", priority=1), Item("c", priority=1)], bump=True)
    assert got == Enqueued(new=1, existing=2, bumped=1, states={"pending": 3})


def test_enqueue_without_bump_leaves_priorities_alone(work: Work) -> None:
    work.add([Item("a", priority=1), Item("b", priority=1)])
    got = work.enqueue([Item("b", priority=0)])
    assert (got.new, got.existing, got.bumped) == (0, 1, 0)
    assert claim_order(work) == ["a", "b"]


def test_enqueue_reports_the_final_status_of_the_given_keys(work: Work) -> None:
    work.add([Item("done"), Item("gone"), Item("todo")])
    finish(work)
    finish(work, ok=False)
    got = work.enqueue([Item("done"), Item("gone"), Item("todo"), Item("fresh"), Item("fresh")], bump=True)
    assert (got.new, got.existing, got.bumped) == (1, 3, 0)
    assert got.states == {"done": 1, "permanent": 1, "pending": 2}


def test_enqueue_a_duplicate_key_in_one_call_counts_once(work: Work) -> None:
    got = work.enqueue([Item("a", priority=1), Item("a", priority=0)], bump=True)
    assert (got.new, got.existing, got.bumped) == (1, 0, 0)
    assert claim_order(work) == ["a"]


def test_add_still_returns_the_count_of_new_keys(work: Work) -> None:
    assert work.add([Item("a"), Item("b")]) == 2
    assert work.add([Item("a"), Item("c")]) == 1


def test_bump_never_uncompletes_a_done_row(work: Work) -> None:
    work.add([Item("a", priority=1), Item("b", priority=1)])
    assert finish(work) == "a"
    assert work.bump(["a", "b"]) == 1
    assert work.progress().done == 1
    assert claim_order(work) == ["b"]


def test_bump_leaves_permanent_and_quarantined_rows_alone(work: Work, clock: ManualClock) -> None:
    work.add([Item("p", priority=1)])
    finish(work, ok=False)
    work.add([Item("q", priority=1)])
    for _ in range(3):  # max_attempts is 3
        clock.now += 10_000
        c = work.claim()
        assert c is not None
        c.finish(Failure(Kind.TRANSIENT, "boom"))
    assert work.bump(["p", "q"]) == 0
    assert claim_order(work) == []


def test_bump_respects_more_urgent_priorities(work: Work) -> None:
    work.add([Item("urgent", priority=-1), Item("same", priority=0), Item("slow", priority=2)])
    assert work.bump(["urgent", "same", "slow", "unknown"], priority=0) == 1
    assert claim_order(work) == ["urgent", "same", "slow"]
    assert work.enqueue([Item("urgent", priority=-1)]).existing == 1  # urgent was not lowered to 0: still claimed first


def test_a_bumped_row_is_claimed_before_older_priority_one_rows(work: Work, clock: ManualClock) -> None:
    work.add([Item("old1", priority=1)])
    clock.now += 1
    work.add([Item("old2", priority=1)])
    clock.now += 1
    work.add([Item("late", priority=1)])
    assert work.bump(["late"]) == 1
    assert claim_order(work) == ["late", "old1", "old2"]


def test_work_fed_from_outside_while_a_worker_is_busy_is_claimed_next(work: Work, tmp_path: Path, clock: ManualClock) -> None:
    work.add([Item(f"p{n}", priority=1) for n in range(3)])
    busy = work.claim()  # a worker holds p0 and the table is not dry
    assert busy is not None
    assert busy.key == "p0"
    clock.now += 1
    seen: list[Enqueued] = []

    def feeder() -> None:
        outside = Work(tmp_path / "work.db", tmp_path / "leases", clock=clock)
        try:
            seen.append(outside.enqueue([Item("late", priority=1)]))
            seen.append(outside.enqueue([Item("late", priority=0), Item("fresh", priority=0)], bump=True))
        finally:
            outside.close()

    thread = threading.Thread(target=feeder)
    thread.start()
    thread.join(timeout=30)
    assert [(e.new, e.existing, e.bumped) for e in seen] == [(1, 0, 0), (1, 1, 1)]
    nxt = work.claim()
    assert nxt is not None
    assert nxt.key == "late"  # bumped, and older than "fresh": not "p1"
    nxt.release()
    busy.release()
    assert claim_order(work) == ["late", "fresh", "p0", "p1", "p2"]
