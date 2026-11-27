"""Wait for a descriptor with poll(2): select(2) raises ValueError for any descriptor number >= 1024."""

from __future__ import annotations

import math
import select


def _poll(fd: int, flags: int, timeout: float) -> bool:
    poller = select.poll()
    poller.register(fd, flags)
    return bool(poller.poll(max(0, math.ceil(timeout * 1000))))


def readable(fd: int, timeout: float) -> bool:
    """True when a read would not block (data, EOF or error) within ``timeout`` seconds."""
    return _poll(fd, select.POLLIN, timeout)


def writable(fd: int, timeout: float) -> bool:
    """True when a write would not block (or would fail at once) within ``timeout`` seconds."""
    return _poll(fd, select.POLLOUT, timeout)
