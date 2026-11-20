"""Pacer in one process, with the clock and the sleeps injected."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from any_lease import Pacer

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
