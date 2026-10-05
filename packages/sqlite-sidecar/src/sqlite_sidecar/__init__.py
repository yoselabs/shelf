"""SQLite sidecar plumbing: open, transact, code a timestamp, tell damage from busy.

A sidecar store — a derived index, an append-only log, any per-concern state that owns
its own SQLite file — opens it the same way: create the parent dir, pass ``":memory:"``
through, autocommit with explicit transactions, WAL, ``synchronous=NORMAL``, a busy
timeout, any loadable extension it needs. Schema and queries stay with each store; this
is deliberately not a lifecycle base class (the sibling of ``duckdb-sidecar``).

What is here because it was learned, not read:

* :func:`is_corruption` — busy and locked are ``OperationalError``, a subclass of
  ``DatabaseError``, so ``except DatabaseError`` alone treats a busy file as damage.
* :func:`integrity_ok` runs on a fresh connection: a long-lived reader's ``PRAGMA
  integrity_check`` reported a malformed FTS5 index that a fresh connection and the
  writer both called ``ok`` (10 of 40 cycles, while its ``MATCH`` results were right).
* :func:`set_aside` moves ``-wal`` and ``-shm`` with the file: a fresh file opened beside
  an old WAL would replay someone else's pages.
* :func:`to_text` / :func:`from_text`: ``sqlite3``'s default datetime adapter is
  deprecated (3.12) and a value comes back as the text it went in as, so a time column
  is fixed-width ISO text — text order is then time order — coded in one place.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from itertools import count
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import threading
    from collections.abc import Callable, Generator, Mapping

#: The primary result codes that mean the file itself is damaged. Busy and locked are
#: `OperationalError`s too — a subclass of `DatabaseError` — and are not damage.
_DAMAGE_CODES = frozenset({sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB})

#: What travels with a SQLite file: its WAL and the WAL's shared-memory index.
_COMPANIONS = ("-wal", "-shm")

_TEXT_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

_savepoints = count()


class ExtensionUnavailableError(RuntimeError):
    """A loadable extension a store needs could not be loaded into this ``sqlite3``."""

    def __init__(self, extension: str, cause: BaseException) -> None:
        super().__init__(f"the SQLite extension {extension!r} could not be loaded (this Python's sqlite3 must allow extensions): {cause}")
        self.extension = extension


def connect(
    target: Path | str,
    *,
    extensions: Mapping[str, Callable[[sqlite3.Connection], object]] | None = None,
    read_only: bool = False,
    timeout: float = 10.0,
) -> sqlite3.Connection:
    """Open a sidecar connection: autocommit, WAL, ``synchronous=NORMAL``, extensions loaded.

    A file target gets its parent directory created; ``":memory:"`` touches no path.
    ``read_only`` opens ``mode=ro``: it reads the last commit and every write fails.
    ``extensions`` maps a name to a loader (``sqlite_vec.load``); a loader that fails
    raises :class:`ExtensionUnavailableError` naming it.
    """
    name = str(target)
    if name == ":memory:":
        conn = sqlite3.connect(name, check_same_thread=False, isolation_level=None, timeout=timeout)
    else:
        path = Path(target)
        if read_only:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False, isolation_level=None, timeout=timeout)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=timeout)
    try:
        _load(conn, extensions or {})
        if not read_only:
            # The first statement that reads the file: one that is not a database fails here.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
    except BaseException:
        conn.close()
        raise
    return conn


def _load(conn: sqlite3.Connection, extensions: Mapping[str, Callable[[sqlite3.Connection], object]]) -> None:
    for extension, loader in extensions.items():
        try:
            conn.enable_load_extension(True)  # noqa: FBT003 — stdlib positional flag
            loader(conn)
            conn.enable_load_extension(False)  # noqa: FBT003
        except (AttributeError, sqlite3.Error) as exc:
            raise ExtensionUnavailableError(extension, exc) from exc


@contextmanager
def transaction(conn: sqlite3.Connection, *, lock: threading.RLock | None = None) -> Generator[sqlite3.Connection]:
    """``BEGIN IMMEDIATE`` … ``COMMIT``, ``ROLLBACK`` on error — or a savepoint inside one.

    Immediate, so the write lock is taken up front and a busy file waits at ``BEGIN``
    rather than failing half-way. Inside an open transaction it nests as a savepoint,
    so a caller can wrap a whole pass around units that are transactions of their own.
    ``lock`` (an ``RLock``) is held for the span, for a connection several threads share.
    """
    if lock is not None:
        lock.acquire()
    try:
        if conn.in_transaction:
            name = f"sp_{next(_savepoints)}"
            conn.execute(f"SAVEPOINT {name}")
            try:
                yield conn
            except BaseException:
                conn.execute(f"ROLLBACK TO {name}")
                conn.execute(f"RELEASE {name}")
                raise
            conn.execute(f"RELEASE {name}")
            return
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
    finally:
        if lock is not None:
            lock.release()


def to_text(value: datetime) -> str:
    """``value`` as ``YYYY-MM-DD HH:MM:SS.ffffff`` in UTC; naive is taken as UTC already.

    Fixed width — four-digit year, six-digit fraction — so text order is time order.
    """
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.isoformat(sep=" ", timespec="microseconds")


def from_text(text: str, *, aware: bool = False) -> datetime:
    """The datetime :func:`to_text` wrote: naive UTC, or ``tzinfo=UTC`` with ``aware``."""
    value = datetime.strptime(text, _TEXT_FORMAT)  # noqa: DTZ007 — the text is UTC by contract; aware adds it
    return value.replace(tzinfo=UTC) if aware else value


def is_corruption(exc: BaseException) -> bool:
    """Whether ``exc`` says the SQLite file is damaged (corrupt, or not a database at all).

    Never a busy or locked database: those are `OperationalError`, a `DatabaseError`
    subclass, and waiting is their cure, not a rebuild.
    """
    code = cast("int | None", getattr(exc, "sqlite_errorcode", None)) if isinstance(exc, sqlite3.DatabaseError) else None
    return code is not None and code & 0xFF in _DAMAGE_CODES


def unreadable(path: Path) -> bool:
    """Whether a file exists at ``path`` that SQLite cannot open as a database.

    A probe on a fresh read-only connection, cheap enough for every start: it reads the
    header and the schema, not every page (that is :func:`integrity_ok`).
    """
    if not path.exists():
        return False
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlite3.DatabaseError as exc:
        return is_corruption(exc)
    finally:
        conn.close()
    return False


def integrity_ok(path: Path, *, extra: Callable[[sqlite3.Connection], object] | None = None) -> bool:
    """Whether the file passes ``PRAGMA integrity_check`` and ``extra`` (which raises to fail).

    Always on a fresh connection, never a long-lived one (see the module docstring).
    """
    try:
        conn = sqlite3.connect(f"file:{path}?mode=rw", uri=True, isolation_level=None)
    except sqlite3.Error:
        return False
    try:
        if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            return False
        if extra is not None:
            extra(conn)
    except sqlite3.Error:
        return False
    finally:
        conn.close()
    return True


def set_aside(path: Path, *, at: datetime | None = None) -> list[Path]:
    """Move the file and its ``-wal``/``-shm`` to ``<name>.corrupt-<UTC stamp>``; return where.

    Kept for a post-mortem, never deleted. The next open starts an empty file.
    """
    stamp = (at or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    moved: list[Path] = []
    for src in (path, *(path.with_name(path.name + sfx) for sfx in _COMPANIONS)):
        if src.exists():
            dst = src.with_name(f"{src.name}.corrupt-{stamp}")
            src.rename(dst)
            moved.append(dst)
    return moved


__all__ = [
    "ExtensionUnavailableError",
    "connect",
    "from_text",
    "integrity_ok",
    "is_corruption",
    "set_aside",
    "to_text",
    "transaction",
    "unreadable",
]
