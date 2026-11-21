"""Pacer in one process, with the clock and the sleeps injected."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest

from any_lease import Pacer, PaceStatus

if TYPE_CHECKING:
    from pathlib import Path


class FakeTime:
    """A clock that only moves when something sleeps."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    async def asleep(self, seconds: float) -> None:
        self.sleep(seconds)


def test_the_first_pass_is_free_and_each_next_waits_one_interval(tmp_path: Path) -> None:
    t = FakeTime()
    pacer = Pacer(tmp_path, clock=t.clock, sleep=t.sleep)
    slots = [pacer.wait("proxy/2081", 1.0) for _ in range(3)]
    assert slots == [1000.0, 1001.0, 1002.0]
    assert t.slept == [1.0, 1.0]


def test_time_passed_on_its_own_counts_toward_the_interval(tmp_path: Path) -> None:
    t = FakeTime()
    pacer = Pacer(tmp_path, clock=t.clock, sleep=t.sleep)
    pacer.wait("k", 5.0)
    t.now += 3.0
    pacer.wait("k", 5.0)
    assert t.slept == [2.0]


def test_keys_are_paced_apart_and_two_pacers_on_one_folder_share_a_key(tmp_path: Path) -> None:
    t = FakeTime()
    one, two = Pacer(tmp_path, clock=t.clock, sleep=t.sleep), Pacer(tmp_path, clock=t.clock, sleep=t.sleep)
    one.wait("a", 1.0)
    two.wait("b", 1.0)
    assert t.slept == []
    two.wait("a", 1.0)
    assert t.slept == [1.0]


def test_callers_reserve_queued_slots_before_any_sleeps(tmp_path: Path) -> None:
    t = FakeTime()
    pacer = Pacer(tmp_path, clock=t.clock, sleep=lambda s: None)
    assert [pacer.wait("k", 2.0) for _ in range(3)] == [1000.0, 1002.0, 1004.0]  # the clock never moved: three queued at spacing


def test_reserve_books_slots_without_sleeping(tmp_path: Path) -> None:
    t = FakeTime()
    pacer = Pacer(tmp_path, clock=t.clock, sleep=t.sleep)
    assert [pacer.reserve("k", 2.0) for _ in range(3)] == [1000.0, 1002.0, 1004.0]
    assert t.slept == []
    assert pacer.wait("k", 2.0) == 1006.0  # the booked slots stay booked for a blocking caller too


async def test_apace_sleeps_on_the_async_sleep_not_the_blocking_one(tmp_path: Path) -> None:
    t = FakeTime()

    def blocking(_: float) -> None:
        pytest.fail("apace must not call the blocking sleep")

    pacer = Pacer(tmp_path, clock=t.clock, sleep=blocking, asleep=t.asleep)
    assert [await pacer.apace("k", 1.0) for _ in range(2)] == [1000.0, 1001.0]
    assert t.slept == [1.0]


def test_a_negative_interval_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="negative"):
        Pacer(tmp_path).wait("k", -1.0)


def test_penalize_makes_wait_sleep_through_the_block_then_pace_on(tmp_path: Path) -> None:
    t = FakeTime()
    pacer = Pacer(tmp_path, clock=t.clock, sleep=t.sleep)
    assert pacer.penalize("pool", 60.0, reason="blocked: cookies") == 1060.0
    assert pacer.wait("pool", 1.0) == 1060.0
    assert t.slept == [60.0]
    assert pacer.wait("pool", 1.0) == 1061.0  # the block ended; ordinary spacing resumes
    assert t.slept == [60.0, 1.0]


async def test_apace_and_reserve_honour_the_block(tmp_path: Path) -> None:
    t = FakeTime()
    pacer = Pacer(tmp_path, clock=t.clock, sleep=t.sleep, asleep=t.asleep)
    pacer.penalize("pool", 30.0)
    assert pacer.reserve("pool", 2.0) == 1030.0
    assert t.slept == []
    assert await pacer.apace("pool", 2.0) == 1032.0
    assert t.slept == [32.0]


def test_penalize_takes_the_max_and_never_shortens(tmp_path: Path) -> None:
    t = FakeTime()
    pacer = Pacer(tmp_path, clock=t.clock, sleep=t.sleep)
    assert pacer.penalize("k", 100.0, reason="long") == 1100.0
    assert pacer.penalize("k", 10.0, reason="short") == 1100.0
    assert pacer.blocked_until("k") == 1100.0
    assert pacer.status("k").reason == "long"
    t.now += 50.0
    assert pacer.penalize("k", 80.0, reason="longer") == 1130.0  # now + 80 beats what is left
    assert pacer.status("k").reason == "longer"


def test_a_negative_penalty_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="negative"):
        Pacer(tmp_path).penalize("k", -1.0)


def test_the_block_is_visible_from_a_second_pacer_on_the_same_root(tmp_path: Path) -> None:
    t = FakeTime()
    one, two = Pacer(tmp_path, clock=t.clock, sleep=t.sleep), Pacer(tmp_path, clock=t.clock, sleep=t.sleep)
    one.penalize("pool", 40.0, reason="blocked")
    assert two.blocked_until("pool") == 1040.0
    assert two.wait("pool", 1.0) == 1040.0
    assert t.slept == [40.0]
    assert two.blocked_until("other") is None  # keys are blocked apart


def test_a_block_that_has_passed_is_no_block(tmp_path: Path) -> None:
    t = FakeTime()
    pacer = Pacer(tmp_path, clock=t.clock, sleep=t.sleep)
    pacer.penalize("k", 5.0, reason="x")
    t.now += 5.0
    assert pacer.blocked_until("k") is None
    assert pacer.status("k").reason == ""


def test_an_unpenalized_key_paces_exactly_as_before(tmp_path: Path) -> None:
    t = FakeTime()
    pacer = Pacer(tmp_path, clock=t.clock, sleep=t.sleep)
    assert pacer.blocked_until("k") is None
    assert [pacer.wait("k", 1.0) for _ in range(3)] == [1000.0, 1001.0, 1002.0]
    assert t.slept == [1.0, 1.0]


def test_clear_lifts_the_block_and_leaves_the_slots(tmp_path: Path) -> None:
    t = FakeTime()
    pacer = Pacer(tmp_path, clock=t.clock, sleep=t.sleep)
    pacer.wait("k", 5.0)
    pacer.penalize("k", 100.0)
    pacer.clear("k")
    pacer.clear("k")  # already clear
    assert pacer.blocked_until("k") is None
    assert pacer.wait("k", 5.0) == 1005.0  # the earlier booking still stands


def test_status_books_no_slot_and_creates_no_file(tmp_path: Path) -> None:
    t = FakeTime()
    pacer = Pacer(tmp_path, clock=t.clock, sleep=t.sleep)
    assert pacer.status("k") == PaceStatus(next_slot=1000.0, blocked_until=None, reason="")
    assert list(tmp_path.iterdir()) == []
    pacer.wait("k", 3.0)
    assert pacer.status("k").next_slot == 1003.0
    assert pacer.status("k").next_slot == 1003.0  # reading twice changes nothing
    assert pacer.wait("k", 3.0) == 1003.0
    pacer.penalize("k", 30.0, reason="blocked")
    assert pacer.status("k") == PaceStatus(next_slot=1033.0, blocked_until=1033.0, reason="blocked")  # now is 1003 after the sleep
    with pytest.raises(AttributeError):
        pacer.status("k").reason = "x"  # type: ignore[misc]  # frozen


_PENALIZER = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    from any_lease import PaceStatus, Pacer
    print(Pacer(Path(sys.argv[1])).penalize("pool", 600.0, reason="from a child"), flush=True)
    """
)


def test_a_block_set_by_another_process_is_seen_here(tmp_path: Path) -> None:
    out = subprocess.run([sys.executable, "-c", _PENALIZER, str(tmp_path)], capture_output=True, text=True, check=True).stdout
    until = float(out)
    assert Pacer(tmp_path).blocked_until("pool") == until
    assert Pacer(tmp_path).status("pool").reason == "from a child"
