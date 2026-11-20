"""The table's rules at its public surface: add, claim, finish, progress."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from any_work import Claimed, Failure, Item, Kind, Status, Work

if TYPE_CHECKING:
    from pathlib import Path

    from any_work.testing import ManualClock


def take(work: Work, kind: str | None = None) -> Claimed:
    claimed = work.claim(kind)
    assert claimed is not None
    return claimed


def claim_all(work: Work) -> list[str]:
    """Keys in the order claim hands them out; every claim stays held so the next one moves on."""
    got = []
    while (c := work.claim()) is not None:
        got.append(c)
    keys = [c.key for c in got]
    for c in got:
        c.release()
    return keys


def fail(work: Work, clock: ManualClock, kind: Kind, times: int) -> None:
    for _ in range(times):
        clock.now += 10_000  # past any backoff
        claimed = work.claim()
        assert claimed is not None
        claimed.finish(Failure(kind, "boom 17"))


def test_add_is_idempotent_and_leaves_an_existing_key_untouched(work: Work) -> None:
    assert work.add([Item("a", payload={"n": 1}), Item("b")]) == 2
    first = work.claim()
    assert first is not None
    first.finish()
    assert work.add([Item("a", kind="other", payload={"n": 2}, priority=9), Item("c")]) == 1
    p = work.progress()
    assert (p.total, p.done, p.by_status[Status.PENDING]) == (3, 1, 2)
    assert "other" not in p.by_kind


def test_payload_round_trips_as_json(work: Work) -> None:
    work.add([Item("a", payload={"url": "https://x", "n": [1, 2]})])
    with take(work) as c:
        assert (c.key, c.kind, c.payload, c.attempts) == ("a", "default", {"url": "https://x", "n": [1, 2]}, 0)


def test_claim_order_is_priority_then_due_time_then_insertion(work: Work, clock: ManualClock) -> None:
    work.add([Item("late-low", priority=1)])
    clock.now += 5
    work.add([Item("b1"), Item("b2")])
    clock.now -= 10  # an item added "earlier" in time, inserted last
    work.add([Item("early")])
    clock.now += 10
    assert claim_all(work) == ["early", "b1", "b2", "late-low"]


def test_claim_takes_only_the_asked_kind(work: Work) -> None:
    work.add([Item("v", kind="video"), Item("c", kind="channel")])
    with take(work, "channel") as c:
        assert c.key == "c"
        assert work.claim("channel") is None
    assert [work.claim("video") is not None, work.claim("nothing")] == [True, None]


def test_a_key_held_by_another_claim_is_skipped(work: Work) -> None:
    work.add([Item("a"), Item("b")])
    first = work.claim()
    assert first is not None
    with first:
        second = work.claim()
        assert second is not None
        with second:
            assert second.key != first.key
            assert work.claim() is None


def test_leaving_without_finish_keeps_the_row_pending_and_claimable(work: Work) -> None:
    work.add([Item("a")])
    with take(work):
        pass
    again = work.claim()
    assert again is not None
    assert again.attempts == 0
    again.release()


def test_finish_twice_is_refused(work: Work) -> None:
    work.add([Item("a")])
    c = work.claim()
    assert c is not None
    c.finish()
    with pytest.raises(RuntimeError, match="already finished"):
        c.finish()


@pytest.mark.parametrize(
    ("kind", "times", "status", "attempts"),
    [
        (Kind.TRANSIENT, 1, Status.PENDING, 1),
        (Kind.TRANSIENT, 2, Status.PENDING, 2),
        (Kind.TRANSIENT, 3, Status.QUARANTINED, 3),  # the cap: max_attempts=3
        (Kind.UNKNOWN, 1, Status.PENDING, 1),
        (Kind.UNKNOWN, 3, Status.QUARANTINED, 3),  # never permanent
        (Kind.PERMANENT, 1, Status.PERMANENT, 1),
    ],
)
def test_finish_rules_per_failure_kind(work: Work, clock: ManualClock, *, kind: Kind, times: int, status: Status, attempts: int) -> None:
    work.add([Item("k")])
    fail(work, clock, kind, times)
    p = work.progress()
    assert p.by_status[status] == 1
    assert p.total == 1
    if status is Status.PENDING:
        (row,) = work.retry_view()
        assert row.attempts == attempts
        assert row.last_error == "boom 17"


def test_ok_is_done_and_never_claimed_again(work: Work, clock: ManualClock) -> None:
    work.add([Item("k")])
    c = work.claim()
    assert c is not None
    c.finish()
    clock.now += 1_000_000
    assert work.claim() is None
    assert work.progress().done == 1


def test_a_failed_item_waits_its_backoff_by_the_injected_clock(work: Work, clock: ManualClock) -> None:
    work.add([Item("k")])
    for attempt in range(2):
        failed_at = clock.now
        c = work.claim()
        assert c is not None
        c.finish(Failure(Kind.TRANSIENT, "slow"))
        due = failed_at + 10 * 2**attempt  # base 10, doubled per attempt, jitter factor 1
        (row,) = work.retry_view()
        assert row.next_try_at == due
        clock.now = due - 0.001
        assert work.claim() is None
        clock.now = due


def test_the_backoff_cap_bounds_the_wait(tmp_path: Path, clock: ManualClock) -> None:
    table = Work(tmp_path / "w.db", tmp_path / "l", clock=clock, rand=lambda: 0.5, max_attempts=10, backoff_base=10.0, backoff_cap=100.0)
    table.add([Item("k")])
    waits = []
    for _ in range(6):
        failed_at = clock.now
        c = table.claim()
        assert c is not None
        c.finish(Failure(Kind.TRANSIENT, "slow"))
        (row,) = table.retry_view()
        waits.append(row.next_try_at - failed_at)
        clock.now = row.next_try_at
    table.close()
    assert waits == [10, 20, 40, 80, 100, 100]


def test_failure_fingerprint_is_stored_for_a_permanent_stop(work: Work) -> None:
    work.add([Item("k")])
    c = work.claim()
    assert c is not None
    failure = Failure(Kind.PERMANENT, "video 4411 removed")
    c.finish(failure)
    assert failure.fp == Failure(Kind.PERMANENT, "video 9 removed").fp
    assert work.progress().by_status[Status.PERMANENT] == 1


def test_progress_counts_per_status_and_per_kind_and_retry_view_lists_the_waiting(work: Work, clock: ManualClock) -> None:
    work.add([Item("v1", kind="video"), Item("v2", kind="video"), Item("c1", kind="channel"), Item("v3", kind="video")])
    plan: dict[str, Failure | None] = {"v1": None, "v2": Failure(Kind.PERMANENT, "gone"), "c1": Failure(Kind.TRANSIENT, "429")}
    for _ in plan:
        c = work.claim()
        assert c is not None
        c.finish(plan[c.key])
    p = work.progress()
    assert p.by_status == {Status.PENDING: 2, Status.DONE: 1, Status.PERMANENT: 1, Status.QUARANTINED: 0}
    assert p.by_kind["video"][Status.DONE] == 1
    assert p.by_kind["video"][Status.PERMANENT] == 1
    assert p.by_kind["video"][Status.PENDING] == 1
    assert p.by_kind["channel"][Status.PENDING] == 1
    assert [(r.key, r.attempts, r.last_error) for r in work.retry_view()] == [("c1", 1, "429")]


def test_more_due_items_than_one_scan_page_are_all_reached(work: Work) -> None:
    work.add([Item(f"k{i:04}") for i in range(150)])
    assert len(claim_all(work)) == 150
