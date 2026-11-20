"""Pacing across processes: at most one pass per ``every`` seconds on a key, whoever the caller."""

from __future__ import annotations

import asyncio
import fcntl
import os
import time
from typing import TYPE_CHECKING

from any_lease._keyfile import keyfile

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path


class Pacer:
    """Slots reserved under a file lock: ``<root>/<keyfile>.pace`` holds the next wall-clock time a pass is allowed.

    A caller takes the lock, reserves ``max(now, next)``, stores ``slot + every``, releases the lock, and only then sleeps until
    its slot. N callers queue at ``every`` spacing instead of all waking together. The lock is held for a read and a write, never
    for the sleep. ``clock`` is wall time (``time.time``) because processes must agree on it; ``sleep`` and ``asleep`` are
    injected for tests.
    A key that is never passed again leaves its small file behind; files are the state, there is nothing to expire.
    """

    def __init__(
        self,
        root: Path,
        *,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], object] = time.sleep,
        asleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    ) -> None:
        self.root = root
        self._clock = clock
        self._sleep = sleep
        self._asleep = asleep

    def reserve(self, key: str, every: float) -> float:
        """Book the next slot on ``key`` and return it (wall-clock seconds) without sleeping, for a queue that sets ``next_try_at``.

        The slot is spent: the next caller is placed ``every`` after it, so the caller must act at or after it, not drop it.
        """
        return self._reserve(key, every)[0]

    def wait(self, key: str, every: float) -> float:
        """Block until at least ``every`` seconds after the previous pass on ``key`` (any process). Returns the slot time reserved."""
        slot, delay = self._reserve(key, every)
        if delay > 0:
            self._sleep(delay)
        return slot

    async def apace(self, key: str, every: float) -> float:
        """:meth:`wait` that sleeps on the event loop; only the brief file lock blocks it."""
        slot, delay = self._reserve(key, every)
        if delay > 0:
            await self._asleep(delay)
        return slot

    def _reserve(self, key: str, every: float) -> tuple[float, float]:
        if every < 0:
            msg = f"every must not be negative, got {every}"
            raise ValueError(msg)
        self.root.mkdir(parents=True, exist_ok=True)
        # A fresh descriptor per call: flock excludes other descriptors, so threads of one process exclude each other too.
        fd = os.open(self.root / f"{keyfile(key)}.pace", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            now = self._clock()
            slot = max(now, _read(fd))
            data = repr(slot + every).encode()
            os.pwrite(fd, data, 0)
            os.ftruncate(fd, len(data))
            return slot, slot - now
        finally:
            os.close(fd)  # drops the flock


def _read(fd: int) -> float:
    try:
        return float(os.pread(fd, 64, 0))
    except ValueError:  # empty (new) or torn by a crash mid-write: no earlier pass is known
        return 0.0
