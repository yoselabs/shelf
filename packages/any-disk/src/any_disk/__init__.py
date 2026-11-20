"""A disk-space guard for a long loop: wait while free space is low, stop when it is very low.

Free space is read with ``shutil.disk_usage(path).free`` and compared in GiB (1024**3 bytes). The two levels give three
zones: ``free >= wait_below_gb`` is room, ``stop_below_gb <= free < wait_below_gb`` waits (polling) for room, and
``free < stop_below_gb`` is a stop. The result is a bool the loop acts on; nothing is raised for a full disk.
"""

from __future__ import annotations

import asyncio
import shutil
import time
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from os import PathLike

__all__ = ["GIB", "Verdict", "await_space", "await_space_async", "space_verdict", "verdict"]

GIB = 1024**3

type Verdict = Literal["room", "wait", "stop"]


class _Usage(Protocol):
    @property
    def free(self) -> int: ...


def _check_levels(wait_below_gb: float, stop_below_gb: float) -> None:
    if stop_below_gb > wait_below_gb:
        msg = f"stop_below_gb ({stop_below_gb}) must not exceed wait_below_gb ({wait_below_gb})"
        raise ValueError(msg)


def verdict(free_gb: float, wait_below_gb: float, stop_below_gb: float) -> Verdict:
    """The pure core: "room" at or above ``wait_below_gb``, "stop" below ``stop_below_gb``, else "wait"."""
    if free_gb >= wait_below_gb:
        return "room"
    return "stop" if free_gb < stop_below_gb else "wait"


def space_verdict(
    path: str | PathLike[str],
    *,
    wait_below_gb: float,
    stop_below_gb: float,
    disk_usage: Callable[[str | PathLike[str]], _Usage] = shutil.disk_usage,
) -> Verdict:
    """One reading of ``path``'s filesystem as "room", "wait" or "stop"; the caller decides what to do and when to look again."""
    _check_levels(wait_below_gb, stop_below_gb)
    return verdict(disk_usage(path).free / GIB, wait_below_gb, stop_below_gb)


def await_space(
    path: str | PathLike[str],
    *,
    wait_below_gb: float,
    stop_below_gb: float,
    poll: float = 300.0,
    on_wait: Callable[[float], object] | None = None,
    sleep: Callable[[float], object] = time.sleep,
    disk_usage: Callable[[str | PathLike[str]], _Usage] = shutil.disk_usage,
) -> bool:
    """True when ``path``'s filesystem has room, waiting ``poll`` seconds at a time while it is between the levels.

    False at once when free space is below ``stop_below_gb``, including when it falls there during a wait.
    ``on_wait(free_gb)`` is called before each sleep. ``stop_below_gb > wait_below_gb`` raises ValueError.
    """
    _check_levels(wait_below_gb, stop_below_gb)
    while True:
        free_gb = disk_usage(path).free / GIB
        zone = verdict(free_gb, wait_below_gb, stop_below_gb)
        if zone != "wait":
            return zone == "room"
        if on_wait is not None:
            on_wait(free_gb)
        sleep(poll)


async def await_space_async(
    path: str | PathLike[str],
    *,
    wait_below_gb: float,
    stop_below_gb: float,
    poll: float = 300.0,
    on_wait: Callable[[float], object] | None = None,
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    disk_usage: Callable[[str | PathLike[str]], _Usage] = shutil.disk_usage,
) -> bool:
    """``await_space`` for an event loop: the same zones, waiting with an awaited ``sleep`` (default ``asyncio.sleep``)."""
    _check_levels(wait_below_gb, stop_below_gb)
    while True:
        free_gb = disk_usage(path).free / GIB
        zone = verdict(free_gb, wait_below_gb, stop_below_gb)
        if zone != "wait":
            return zone == "room"
        if on_wait is not None:
            on_wait(free_gb)
        await sleep(poll)
