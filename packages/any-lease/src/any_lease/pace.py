"""Pacing across processes: at most one pass per ``every`` seconds on a key, whoever the caller."""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from any_lease._keyfile import keyfile

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path


@dataclass(frozen=True)
class PaceStatus:
    """What a key looks like right now, read without booking a slot.

    ``next_slot`` is the wall-clock time :meth:`Pacer.reserve` would return this instant (never before now, never before the
    block ends). ``blocked_until`` is None unless a :meth:`Pacer.penalize` is still running; ``reason`` is that penalty's reason
    (``""`` when none, or none was given).
    """

    next_slot: float
    blocked_until: float | None
    reason: str


class Pacer:
    """Slots reserved under a file lock: ``<root>/<keyfile>.pace`` holds the next wall-clock time a pass is allowed.

    A caller takes the lock, reserves ``max(now, next)``, stores ``slot + every``, releases the lock, and only then sleeps until
    its slot. N callers queue at ``every`` spacing instead of all waking together. The lock is held for a read and a write, never
    for the sleep. ``clock`` is wall time (``time.time``) because processes must agree on it; ``sleep`` and ``asleep`` are
    injected for tests.
    A penalty (:meth:`penalize`) is a shared "blocked until" time kept in ``<root>/<keyfile>.block`` and read and written under that
    same ``.pace`` lock: while it runs, no slot is earlier than its end, so every process sleeps through it together.
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

    def penalize(self, key: str, seconds: float, *, reason: str = "") -> float:
        """Block ``key`` for every process until ``max(existing block, now + seconds)`` and return that wall-clock time.

        Only the max is stored, so a shorter penalty never shortens a longer one (and keeps the longer one's reason). Escalation
        (how long, how often) is the caller's policy. A worker that sees a pool-wide block calls this once; the rest of the
        callers of :meth:`wait`, :meth:`apace` and :meth:`reserve` get slots at or after the returned time.
        """
        if seconds < 0:
            msg = f"seconds must not be negative, got {seconds}"
            raise ValueError(msg)
        fd = self._open(key)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            until, _ = self._read_block(key)
            wanted = self._clock() + seconds
            if until is not None and until >= wanted:
                return until
            self._write_block(key, wanted, reason)
            return wanted
        finally:
            os.close(fd)

    def blocked_until(self, key: str) -> float | None:
        """The wall-clock time until which ``key`` is blocked, or None when it is not (a read under the lock)."""
        return self.status(key).blocked_until

    def clear(self, key: str) -> None:
        """Drop the block on ``key``, for a manual reset. The pacing slot is left as it is."""
        fd = self._open(key)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            self._write_block(key, 0.0, "")  # a block that ended long ago: reads as not blocked
        finally:
            os.close(fd)

    def status(self, key: str) -> PaceStatus:
        """The key's next slot and block, read under a shared lock; no slot is booked and no file is created."""
        now = self._clock()
        try:
            fd = os.open(self.root / f"{keyfile(key)}.pace", os.O_RDONLY)
        except FileNotFoundError:  # never paced nor penalized: nothing is known, nothing is blocked
            return PaceStatus(next_slot=now, blocked_until=None, reason="")
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            nxt = _read(fd)
            until, reason = self._read_block(key)
        finally:
            os.close(fd)
        if until is not None and until <= now:
            until, reason = None, ""
        return PaceStatus(next_slot=max(now, nxt, until or 0.0), blocked_until=until, reason=reason)

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
        fd = self._open(key)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            now = self._clock()
            until, _ = self._read_block(key)
            slot = max(now, _read(fd), until or 0.0)
            data = repr(slot + every).encode()
            os.pwrite(fd, data, 0)
            os.ftruncate(fd, len(data))
            return slot, slot - now
        finally:
            os.close(fd)  # drops the flock

    def _open(self, key: str) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        # A fresh descriptor per call: flock excludes other descriptors, so threads of one process exclude each other too.
        return os.open(self.root / f"{keyfile(key)}.pace", os.O_RDWR | os.O_CREAT, 0o600)

    def _block_path(self, key: str) -> Path:
        return self.root / f"{keyfile(key)}.block"

    def _read_block(self, key: str) -> tuple[float | None, str]:
        """(until, reason) from the block file; (None, "") when there is none or a crash tore it. Call with the ``.pace`` lock held."""
        try:
            record = json.loads(self._block_path(key).read_text(encoding="utf-8"))
            return float(record["until"]), str(record["reason"])
        except (FileNotFoundError, ValueError, KeyError, TypeError):  # absent, or torn by a crash mid-write: not blocked
            return None, ""

    def _write_block(self, key: str, until: float, reason: str) -> None:
        path = self._block_path(key)
        tmp = path.with_suffix(".block.tmp")  # one writer at a time under the .pace lock
        tmp.write_text(json.dumps({"until": until, "reason": reason}), encoding="utf-8")
        tmp.replace(path)


def _read(fd: int) -> float:
    try:
        return float(os.pread(fd, 64, 0))
    except ValueError:  # empty (new) or torn by a crash mid-write: no earlier pass is known
        return 0.0
