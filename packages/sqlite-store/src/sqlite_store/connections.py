"""Process, thread and file ownership for reusable SQLite writers."""

from __future__ import annotations

import os
import sqlite3
from _thread import RLock, _local, get_ident
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Callable

Key: TypeAlias = tuple[int, int, Path, int, int]


class ThreadOwner(_local):
    def __init__(self) -> None:
        super().__init__()
        self.owner = object()


class SharedConnections:
    """Cache idle writers; callers own their short transactions."""

    def __init__(self) -> None:
        self.connections: dict[Key, tuple[sqlite3.Connection, object]] = {}
        self.lock = RLock()
        self.local = ThreadOwner()

    def after_fork(self) -> None:
        """Replace a lock that may belong to a vanished thread in the parent."""
        self.lock = RLock()

    @staticmethod
    def key_of(path: Path) -> Key:
        stat = path.stat()
        return os.getpid(), get_ident(), path, stat.st_dev, stat.st_ino

    @staticmethod
    def usable(con: sqlite3.Connection) -> bool:
        try:
            idle = not con.in_transaction
        except sqlite3.Error:
            return False
        else:
            return idle

    def drop(self, key: Key) -> None:
        con, _ = self.connections.pop(key)
        with suppress(sqlite3.Error):
            con.close()

    def get(self, path: str | os.PathLike[str], opener: Callable[[Path], sqlite3.Connection | None]) -> sqlite3.Connection | None:
        with self.lock:
            try:
                con = self._get(Path(path).resolve(), opener)
            except (OSError, ValueError, RuntimeError):
                return None
            else:
                return con

    def _get(self, target: Path, opener: Callable[[Path], sqlite3.Connection | None]) -> sqlite3.Connection | None:
        prefix = os.getpid(), get_ident(), target
        try:
            key = self.key_of(target)
        except FileNotFoundError:
            key = None
        for old, (con, owner) in tuple(self.connections.items()):
            if old[:3] == prefix:
                if old == key and owner is self.local.owner and self.usable(con):
                    return con
                self.drop(old)
        con = opener(target)
        if con is not None:
            try:
                key = self.key_of(target)
            except OSError:
                con.close()
                raise
            self.connections[key] = con, self.local.owner
        return con

    def discard(self, con: sqlite3.Connection) -> None:
        with self.lock:
            for key, (cached, _) in tuple(self.connections.items()):
                if key[0] == os.getpid() and cached is con:
                    self.drop(key)

    def close(self) -> None:
        """Close this process's writers after operations on all threads stop."""
        with self.lock:
            for key in tuple(self.connections):
                if key[0] == os.getpid():
                    self.drop(key)
