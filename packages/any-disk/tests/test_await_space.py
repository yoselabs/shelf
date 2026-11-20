"""await_space and await_space_async: three zones, driven by a scripted disk and a recording sleep."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from any_disk import GIB, await_space, await_space_async, space_verdict, verdict

if TYPE_CHECKING:
    from pathlib import Path

WAIT, STOP = 50.0, 40.0


class Disk:
    """A scripted disk: each read returns the next free-GiB value (the last repeats); records every sleep."""

    def __init__(self, *free_gb: float) -> None:
        self.script = list(free_gb)
        self.reads = 0
        self.slept: list[float] = []
        self.waited: list[float] = []

    def usage(self, _path: object) -> SimpleNamespace:
        value = self.script[min(self.reads, len(self.script) - 1)]
        self.reads += 1
        return SimpleNamespace(free=int(value * GIB))

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)

    async def asleep(self, seconds: float) -> None:
        self.slept.append(seconds)


# name, script of free GiB, result, polls slept, free values reported to on_wait
CASES = [
    ("room at once", [80], True, 0, []),
    ("exactly the wait level is room", [50], True, 0, []),
    ("exactly the stop level waits", [40, 60], True, 1, [40.0]),
    ("below stop at once", [10], False, 0, []),
    ("waits then recovers", [45, 44, 51], True, 2, [45.0, 44.0]),
    ("waits then drops below stop", [45, 39], False, 1, [45.0]),
]
IDS = [c[0] for c in CASES]


@pytest.mark.parametrize(("name", "script", "result", "polls", "reported"), CASES, ids=IDS)
def test_zones_sync(name: str, script: list[float], result: bool, polls: int, reported: list[float]) -> None:
    disk = Disk(*script)
    got = await_space(
        "/x",
        wait_below_gb=WAIT,
        stop_below_gb=STOP,
        poll=7.0,
        on_wait=disk.waited.append,
        sleep=disk.sleep,
        disk_usage=disk.usage,
    )
    assert (got, disk.slept, disk.waited) == (result, [7.0] * polls, reported), name


@pytest.mark.parametrize(("name", "script", "result", "polls", "reported"), CASES, ids=IDS)
async def test_zones_async(name: str, script: list[float], result: bool, polls: int, reported: list[float]) -> None:
    disk = Disk(*script)
    got = await await_space_async(
        "/x",
        wait_below_gb=WAIT,
        stop_below_gb=STOP,
        poll=7.0,
        on_wait=disk.waited.append,
        sleep=disk.asleep,
        disk_usage=disk.usage,
    )
    assert (got, disk.slept, disk.waited) == (result, [7.0] * polls, reported), name


def test_stop_above_wait_is_refused() -> None:
    with pytest.raises(ValueError, match="stop_below_gb"):
        await_space("/x", wait_below_gb=10, stop_below_gb=20)


async def test_stop_above_wait_is_refused_async() -> None:
    with pytest.raises(ValueError, match="stop_below_gb"):
        await await_space_async("/x", wait_below_gb=10, stop_below_gb=20)


def test_equal_levels_never_wait() -> None:
    disk = Disk(30, 60)
    assert await_space("/x", wait_below_gb=40, stop_below_gb=40, sleep=disk.sleep, disk_usage=disk.usage) is False
    assert disk.slept == []


def test_real_disk_with_tiny_thresholds(tmp_path: Path) -> None:
    assert await_space(tmp_path, wait_below_gb=0.0, stop_below_gb=0.0) is True
    assert await_space(tmp_path, wait_below_gb=1e12, stop_below_gb=1e12) is False


@pytest.mark.parametrize(
    ("free", "expected"),
    [(80.0, "room"), (50.0, "room"), (49.9, "wait"), (40.0, "wait"), (39.9, "stop"), (0.0, "stop")],
)
def test_verdict_table(free: float, expected: str) -> None:
    assert verdict(free, WAIT, STOP) == expected
    assert space_verdict("/x", wait_below_gb=WAIT, stop_below_gb=STOP, disk_usage=Disk(free).usage) == expected
