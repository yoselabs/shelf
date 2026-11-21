"""The work table: one SQLite file for the rows, one flock per key for who is working it."""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Self, assert_never

from any_failure_fp import backoff
from any_lease import Held, Leases
from sqlite_store import Schema, Store

from any_work.model import Enqueued, Failure, Item, Kind, Progress, RetryRow, Status

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable, Iterable, Iterator

# Short transactions only: nothing here calls out while a write lock is held. DDL has no ';' inside a statement (sqlite-store splits on it).
_SCHEMA = Schema(
    version=1,
    name="any-work",
    ddl="""
        CREATE TABLE work (
            key TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('pending', 'done', 'permanent', 'quarantined')),
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            fp TEXT,
            next_try_at REAL NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0,
            payload TEXT NOT NULL
        );
        CREATE INDEX work_due ON work (status, priority, next_try_at)
    """,
    steps={},
)
_CHUNK = 500  # keys per IN (...) list: far below SQLite's bound-variable limit
_PAGE = 64  # candidates read per scan; a held key is skipped, so a page may be all held
_LOCK_LABEL = "any-work"


def _chunks(keys: list[str]) -> Iterator[list[str]]:
    for start in range(0, len(keys), _CHUNK):
        yield keys[start : start + _CHUNK]


def _marks(keys: list[str]) -> str:
    return ",".join("?" * len(keys))


@dataclass
class Claimed:
    """One key this process holds. Call :meth:`finish`; leaving the ``with`` block or dying first keeps the row pending."""

    key: str
    kind: str
    payload: object
    attempts: int
    _work: Work = field(repr=False)
    _held: Held = field(repr=False)
    finished: bool = False

    def finish(self, failure: Failure | None = None) -> None:
        """Record the outcome (``failure``, or ok when None), then release the key.

        The row is written before the flock goes, so the next claimer sees it.
        """
        if self.finished:
            message = f"{self.key!r} is already finished"
            raise RuntimeError(message)
        try:
            self._work.record(self.key, failure)
            self.finished = True
        finally:
            self._held.release()

    def release(self) -> None:
        self._held.release()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


class Work:
    """The table at ``db_path``; liveness is a per-key flock under ``lease_root``. One host, any number of processes.

    ``clock`` is wall time (processes must agree). A transient or unknown failure schedules the retry
    ``backoff(backoff_base, backoff_cap, attempt, rand)`` seconds ahead, and the ``max_attempts``-th failure quarantines the row.
    """

    def __init__(
        self,
        db_path: Path,
        lease_root: Path,
        *,
        clock: Callable[[], float] = time.time,
        rand: Callable[[], float] = random.random,
        max_attempts: int = 5,
        backoff_base: float = 30.0,
        backoff_cap: float = 3600.0,
    ) -> None:
        self._store = Store(_SCHEMA)
        con = self._store.open_rw(db_path)
        if con is None:
            message = f"work table unavailable at {db_path}"
            raise OSError(message)
        self._con: sqlite3.Connection = con
        self._leases = Leases(Path(lease_root))
        self.clock = clock
        self._rand = rand
        self._max_attempts = max_attempts
        self._base = backoff_base
        self._cap = backoff_cap

    def close(self) -> None:
        self._con.close()

    def add(self, items: Iterable[Item]) -> int:
        """Insert items that are not there yet and return how many were new. An existing key is left exactly as it is.

        A feeder should call :meth:`enqueue`, whose return value says what happened to each key.
        """
        return self.enqueue(items).new

    def enqueue(self, items: Iterable[Item], *, bump: bool = False) -> Enqueued:
        """Insert items that are not there yet, in one transaction, and say what happened.

        An existing key keeps its payload, kind and status. With ``bump`` an existing pending row moves to the item's priority when
        that is more urgent (see :meth:`bump`). The result counts new, existing and bumped keys and the final status of every given key.
        """
        now = self.clock()
        given = list(items)
        keys = list(dict.fromkeys(i.key for i in given))
        rows = [(i.key, i.kind, now, i.priority, json.dumps(i.payload)) for i in given]
        with self._store.begin_immediate(self._con):
            existing: set[str] = set()
            for chunk in _chunks(keys):
                found = self._con.execute(f"SELECT key FROM work WHERE key IN ({_marks(chunk)})", chunk)  # noqa: S608 - only '?' marks
                existing.update(k for (k,) in found)
            before = self._con.total_changes
            self._con.executemany(
                "INSERT OR IGNORE INTO work (key, kind, status, next_try_at, priority, payload) VALUES (?, ?, 'pending', ?, ?, ?)",
                rows,
            )
            new = self._con.total_changes - before
            bumped = 0
            if bump:
                for item in given:
                    if item.key in existing:
                        bumped += self._bump(item.key, item.priority)
            states: dict[str, int] = {}
            for chunk in _chunks(keys):
                for status, n in self._con.execute(
                    f"SELECT status, COUNT(*) FROM work WHERE key IN ({_marks(chunk)}) GROUP BY status",  # noqa: S608 - only '?' marks
                    chunk,
                ):
                    states[status] = states.get(status, 0) + n
            return Enqueued(new=new, existing=len(keys) - new, bumped=bumped, states=states)

    def bump(self, keys: Iterable[str], priority: int = 0) -> int:
        """Move pending rows to ``priority`` when it is more urgent than theirs; return how many moved.

        A done, permanent or quarantined row, a row already at or more urgent than ``priority`` (lower is more urgent) and an unknown key
        are untouched.
        """
        with self._store.begin_immediate(self._con):
            return sum(self._bump(k, priority) for k in dict.fromkeys(keys))

    def _bump(self, key: str, priority: int) -> int:
        sql = "UPDATE work SET priority = ? WHERE key = ? AND status = 'pending' AND priority > ?"
        return self._con.execute(sql, (priority, key, priority)).rowcount

    def claim(self, kind: str | None = None) -> Claimed | None:
        """The next due pending item (priority, then due time, then insertion) whose key no other process holds, or None."""
        now = self.clock()
        after: tuple[int, float, int] = (-(2**62), float("-inf"), 0)
        while True:
            page = self._due(now, kind, after)
            for key, *_ in page:
                held = self._leases.try_claim(key, label=_LOCK_LABEL)
                if held is None:
                    continue
                # Re-read under the flock: the previous holder may have finished the row between our scan and our claim.
                row = self._con.execute(
                    "SELECT kind, attempts, payload FROM work WHERE key = ? AND status = 'pending' AND next_try_at <= ?", (key, now)
                ).fetchone()
                if row is None:
                    held.release()
                    continue
                return Claimed(key, row[0], json.loads(row[2]), row[1], self, held)
            if len(page) < _PAGE:
                return None
            after = page[-1][1:]

    def _due(self, now: float, kind: str | None, after: tuple[int, float, int]) -> list[tuple[str, int, float, int]]:
        # Keyset paging on the order key: concurrent finishes shift rows, and an offset would skip some.
        where, args = ("AND kind = ?", (kind,)) if kind is not None else ("", ())
        rows = self._con.execute(
            "SELECT key, priority, next_try_at, rowid FROM work "  # noqa: S608 - the only interpolated text is a constant
            f"WHERE status = 'pending' AND next_try_at <= ? {where} AND (priority, next_try_at, rowid) > (?, ?, ?) "
            "ORDER BY priority, next_try_at, rowid LIMIT ?",
            (now, *args, *after, _PAGE),
        )
        return [(r[0], r[1], r[2], r[3]) for r in rows]

    def record(self, key: str, failure: Failure | None) -> None:
        with self._store.begin_immediate(self._con):
            found = self._con.execute("SELECT attempts FROM work WHERE key = ?", (key,)).fetchone()
            if found is None:
                message = f"no row for {key!r}"
                raise KeyError(message)
            attempts = int(found[0])
            if failure is None:
                self._con.execute("UPDATE work SET status = 'done', attempts = ? WHERE key = ?", (attempts + 1, key))
                return
            status, next_try_at = self._next(failure.kind, attempts)
            self._con.execute(
                "UPDATE work SET status = ?, attempts = ?, last_error = ?, fp = ?, next_try_at = COALESCE(?, next_try_at) WHERE key = ?",
                (status, attempts + 1, failure.error, failure.fp, next_try_at, key),
            )

    def _next(self, kind: Kind, attempts: int) -> tuple[Status, float | None]:
        match kind:
            case Kind.PERMANENT:
                return Status.PERMANENT, None
            case Kind.TRANSIENT | Kind.UNKNOWN:
                # Unknown is never permanent: a guessed class must not end an item for good.
                if attempts + 1 >= self._max_attempts:
                    return Status.QUARANTINED, None
                return Status.PENDING, self.clock() + backoff(self._base, self._cap, attempts, self._rand)
            case _:
                assert_never(kind)

    def progress(self) -> Progress:
        by_status = dict.fromkeys(Status, 0)
        by_kind: dict[str, dict[Status, int]] = {}
        for kind, status, n in self._con.execute("SELECT kind, status, COUNT(*) FROM work GROUP BY kind, status"):
            by_status[Status(status)] += n
            by_kind.setdefault(kind, dict.fromkeys(Status, 0))[Status(status)] = n
        return Progress(by_status, by_kind)

    def retry_view(self) -> list[RetryRow]:
        """Pending rows that have failed at least once, soonest retry first."""
        rows = self._con.execute(
            "SELECT key, kind, attempts, last_error, next_try_at FROM work "
            "WHERE status = 'pending' AND attempts > 0 ORDER BY next_try_at, rowid"
        )
        return [RetryRow(*r) for r in rows]
