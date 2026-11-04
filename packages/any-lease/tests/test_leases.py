"""One process: units, queuing, cancel, timeout, ordered multi-acquire, holders."""

from __future__ import annotations

import os
import threading
import time
from typing import TYPE_CHECKING

import process_lock
import pytest

from any_lease import LeaseCancelledError, Leases, LeaseTimeoutError, Occupant, Waiting

if TYPE_CHECKING:
    from pathlib import Path

POLL = 0.02


@pytest.fixture
def leases(tmp_path: Path) -> Leases:
    return Leases(tmp_path / "locks")


def _rec(o: Occupant) -> process_lock.Holder:
    assert o.holder is not None
    return o.holder


def _held_here(leases: Leases) -> list[Path]:
    return [p for p in process_lock.held() if leases.root.resolve() in p.parents]


def test_units_are_handed_out_in_slot_order_up_to_the_limit(leases: Leases) -> None:
    with leases.acquire("unity", 2) as a, leases.acquire("unity", 2) as b:
        assert (a.slot, b.slot) == (0, 1)
        assert (a.waited, b.waited) == (0.0, 0.0)


def test_a_full_resource_refuses_at_once_with_timeout_zero(leases: Leases) -> None:
    held = leases.acquire("unity", 1, label="first")
    with pytest.raises(LeaseTimeoutError) as err:
        leases.acquire("unity", 1, timeout=0, poll=POLL)
    assert (err.value.name, err.value.limit) == ("unity", 1)
    assert [(o.slot, _rec(o).pid, _rec(o).label) for o in err.value.occupants] == [(0, os.getpid(), "first")]
    held.release()


def test_release_frees_the_unit_and_is_idempotent(leases: Leases) -> None:
    held = leases.acquire("unity", 1)
    held.release()
    held.release()
    again = leases.acquire("unity", 1, timeout=0)
    assert again.slot == 0


def test_context_manager_releases(leases: Leases) -> None:
    with leases.acquire("unity", 1):
        assert len(leases.holders("unity", 1)) == 1
    assert leases.holders("unity", 1) == ()
    leases.acquire("unity", 1, timeout=0).release()


def test_a_waiter_gets_a_unit_when_one_is_released_and_reports_the_wait(leases: Leases) -> None:
    held = leases.acquire("unity", 1)
    seen: list[Waiting] = []

    def on_wait(w: Waiting) -> None:
        seen.append(w)
        time.sleep(0.1)  # a wait that is measurable
        held.release()  # the holder lets go during the wait, not on a timer that load can reorder

    got = leases.acquire("unity", 1, timeout=10, poll=POLL, on_wait=on_wait)
    assert got.waited >= 0.1
    assert len(seen) == 1
    assert (seen[0].name, seen[0].limit) == ("unity", 1)
    assert [o.holder.pid for o in seen[0].occupants if o.holder] == [os.getpid()]


def test_on_wait_raising_ends_the_wait_holding_nothing(leases: Leases) -> None:
    held = leases.acquire("unity", 1)

    def stop(_: Waiting) -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        leases.acquire("unity", 1, poll=POLL, on_wait=stop)
    held.release()
    leases.acquire("unity", 1, timeout=0).release()


def test_cancel_while_queued_raises_and_holds_nothing(leases: Leases) -> None:
    held = leases.acquire("unity", 1)
    cancel = threading.Event()
    threading.Timer(0.1, cancel.set).start()
    began = time.monotonic()
    with pytest.raises(LeaseCancelledError):
        leases.acquire("unity", 1, cancel=cancel, poll=5)  # cancel wakes the wait, not the poll
    assert time.monotonic() - began < 2
    held.release()
    assert _held_here(leases) == []
    leases.acquire("unity", 1, timeout=0).release()


def test_cancel_already_set_never_takes_a_free_unit(leases: Leases) -> None:
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(LeaseCancelledError):
        leases.acquire("unity", 1, cancel=cancel)
    assert _held_here(leases) == []


def test_threads_never_exceed_the_limit(leases: Leases) -> None:
    inside, peak, lock = 0, 0, threading.Lock()

    def work() -> None:
        nonlocal inside, peak
        with leases.acquire("dotnet", 2, poll=POLL):
            with lock:
                inside += 1
                peak = max(peak, inside)
            time.sleep(0.05)
            with lock:
                inside -= 1

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert peak == 2


def test_acquire_all_takes_names_in_sorted_order_whatever_the_listing(leases: Leases) -> None:
    for wants in ([("b", 1), ("a", 1), ("c", 1)], {"c": 1, "b": 1, "a": 1}):
        with leases.acquire_all(wants) as got:
            assert [h.name for h in got.held] == ["a", "b", "c"]


def test_acquire_all_in_opposite_orders_does_not_deadlock(leases: Leases) -> None:
    done: list[str] = []

    def work(tag: str, wants: list[tuple[str, int]]) -> None:
        for _ in range(20):
            with leases.acquire_all(wants, timeout=120, poll=0.005):
                time.sleep(0.002)
        done.append(tag)

    threads = [
        threading.Thread(target=work, args=("ab", [("a", 1), ("b", 1)])),
        threading.Thread(target=work, args=("ba", [("b", 1), ("a", 1)])),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=150)
    assert sorted(done) == ["ab", "ba"]


def test_acquire_all_that_times_out_part_way_frees_what_it_won(leases: Leases) -> None:
    blocker = leases.acquire("b", 1)
    with pytest.raises(LeaseTimeoutError):
        leases.acquire_all([("a", 1), ("b", 1)], timeout=0.1, poll=POLL)
    assert leases.holders("a", 1) == ()
    leases.acquire("a", 1, timeout=0).release()
    blocker.release()


def test_acquire_all_cancelled_part_way_frees_what_it_won(leases: Leases) -> None:
    blocker = leases.acquire("b", 1)
    cancel = threading.Event()
    threading.Timer(0.1, cancel.set).start()
    with pytest.raises(LeaseCancelledError):
        leases.acquire_all([("a", 1), ("b", 1)], cancel=cancel, poll=POLL)
    leases.acquire("a", 1, timeout=0).release()
    blocker.release()


def test_acquire_all_sums_the_wait(leases: Leases) -> None:
    blocker = leases.acquire("b", 1)
    threading.Timer(0.2, blocker.release).start()
    with leases.acquire_all([("a", 1), ("b", 1)], poll=POLL) as got:
        assert got.waited >= 0.1


def test_holders_names_who_is_in_and_takes_no_lock(leases: Leases) -> None:
    assert leases.holders("unity", 2) == ()
    first = leases.acquire("unity", 2, label="x")
    second = leases.acquire("unity", 2, label="y")
    seen = leases.holders("unity", 2)
    assert [(o.slot, _rec(o).label, _rec(o).meta) for o in seen] == [
        (0, "x", {"name": "unity", "slot": 0}),
        (1, "y", {"name": "unity", "slot": 1}),
    ]
    first.release()
    assert [o.slot for o in leases.holders("unity", 2)] == [1]
    second.release()


@pytest.mark.parametrize("name", ["", "a/b", "../x", ".hidden", "a b"])
def test_a_name_that_is_not_a_plain_token_is_refused(leases: Leases, name: str) -> None:
    with pytest.raises(ValueError, match="resource name"):
        leases.acquire(name, 1)


@pytest.mark.parametrize("limit", [0, -1])
def test_a_limit_below_one_is_refused(leases: Leases, limit: int) -> None:
    with pytest.raises(ValueError, match="limit"):
        leases.acquire("unity", limit)


def test_label_and_meta_are_readable_by_a_waiter(leases: Leases) -> None:
    held = leases.acquire("unity", 1, label="bead-7", meta={"worktree": "/w/a"})
    with pytest.raises(LeaseTimeoutError) as err:
        leases.acquire("unity", 1, timeout=0)
    [only] = err.value.occupants
    assert (_rec(only).label, _rec(only).meta) == ("bead-7", {"worktree": "/w/a", "name": "unity", "slot": 0})
    held.release()


def test_a_declared_limit_is_shared_and_may_be_omitted(leases: Leases) -> None:
    assert leases.declare("unity", 2) == 2
    with leases.acquire("unity") as a, Leases(leases.root).acquire("unity") as b:
        assert (a.slot, b.slot) == (0, 1)
        assert len(leases.holders("unity")) == 2
        with pytest.raises(LeaseTimeoutError):
            leases.acquire("unity", timeout=0)


def test_a_different_limit_than_the_declared_one_is_refused(leases: Leases) -> None:
    leases.acquire("unity", 2).release()
    with pytest.raises(ValueError, match="declared with limit 2, not 3"):
        leases.acquire("unity", 3)
    with pytest.raises(ValueError, match="declared with limit 2, not 1"):
        leases.holders("unity", 1)


def test_an_undeclared_name_cannot_omit_the_limit(leases: Leases) -> None:
    with pytest.raises(ValueError, match="no declared limit"):
        leases.acquire("unity")
    with pytest.raises(ValueError, match="no declared limit"):
        leases.holders("unity")


def test_racing_first_declarers_agree_on_one_limit(leases: Leases) -> None:
    results: list[int | str] = []

    def declare(limit: int) -> None:
        try:
            results.append(leases.declare("unity", limit))
        except ValueError as e:
            results.append(str(e))

    threads = [threading.Thread(target=declare, args=(n,)) for n in (1, 2, 3, 4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    winner = leases.declare("unity")
    assert sorted(r for r in results if isinstance(r, int)) == [winner]
    assert len([r for r in results if isinstance(r, str)]) == 3


def test_acquire_all_takes_declared_names_without_limits(leases: Leases) -> None:
    leases.declare("a", 1)
    leases.declare("b", 2)
    with leases.acquire_all(["b", "a"]) as got:
        assert [h.name for h in got.held] == ["a", "b"]
