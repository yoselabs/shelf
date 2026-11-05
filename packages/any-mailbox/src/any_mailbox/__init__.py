"""A one-slot mailbox in a file.

``post`` merges a message into whatever is waiting, under a process-lock; ``take`` hands the waiting message to one
reader and removes it, under the same lock, so a post made while it is taken is never lost or taken twice; ``peek``
reads without the lock. Bytes in, bytes out: the caller owns the codec and any identity check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from atomic_io import atomic_write_bytes
from process_lock import ProcessLock

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

__all__ = ["Mailbox"]


class Mailbox:
    """The message at ``path``; its lock is ``lock`` (default ``<path>.lock``), taken for ``timeout`` seconds."""

    def __init__(self, path: Path, lock: Path | None = None, *, timeout: float | None = 30.0) -> None:
        self.path = path
        self.lock = lock if lock is not None else path.with_name(path.name + ".lock")
        self.timeout = timeout

    def post(self, update: Callable[[bytes | None], bytes | None]) -> bool:
        """Replace the waiting message with ``update(waiting)`` (``None`` when empty), under the lock.

        ``update`` returning ``None`` leaves the mailbox as it was and ``post`` returns False, so a caller that
        re-checks its identity under the lock can refuse without writing. The write is atomic.
        """
        with self._locked():
            new = update(self._read())
            if new is None:
                return False
            atomic_write_bytes(self.path, new, fsync=False)
            return True

    def take(self) -> bytes | None:
        """The waiting message, removed under the lock; ``None`` when empty. Each message is taken once."""
        if not self.path.exists():
            return None
        with self._locked():
            got = self._read()
            self.path.unlink(missing_ok=True)
            return got

    def peek(self) -> bytes | None:
        """The waiting message, left in place, without the lock (atomic writes mean never a torn read)."""
        return self._read()

    def _locked(self) -> ProcessLock:
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        return ProcessLock.acquire(self.lock, timeout=self.timeout, label="any-mailbox", reentrant=False)

    def _read(self) -> bytes | None:
        try:
            return self.path.read_bytes()
        except FileNotFoundError:
            return None
