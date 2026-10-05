# sqlite-sidecar

**Stop repeating the SQLite sidecar dance, and stop rediscovering what SQLite does not
warn you about.** A sidecar store — a derived index, an append-only log, any per-concern
state in its own SQLite file — opens it the same way, transacts the same way, and meets
the same failures. This is the one place that lives. The sibling of `duckdb-sidecar`.

```python
from pathlib import Path
import sqlite_vec
from sqlite_sidecar import connect, transaction, to_text, from_text, is_corruption, set_aside

conn = connect(Path("state/graph.sqlite"))                       # WAL, autocommit, parent dir made
conn = connect(":memory:")                                       # touches no path
conn = connect(path, extensions={"sqlite_vec": sqlite_vec.load})  # ExtensionUnavailableError names it
reader = connect(path, read_only=True)                           # another process's last commit

with transaction(conn):            # BEGIN IMMEDIATE … COMMIT; ROLLBACK on error
    with transaction(conn):        # nested: a savepoint
        conn.execute("INSERT INTO t(at) VALUES (?)", [to_text(when)])

try:
    ...
except sqlite3.DatabaseError as exc:
    if is_corruption(exc):         # corrupt or not a database — never busy or locked
        set_aside(path)            # file, -wal and -shm → *.corrupt-<UTC stamp>
```

Schema and queries stay with each store. Deliberately not a lifecycle base class.
Stdlib only.

## What this package knows

### 1. Busy is a `DatabaseError` too

`is_corruption(exc)`. `database is locked` and `database is busy` are `OperationalError`,
a subclass of `DatabaseError` — so `except sqlite3.DatabaseError` alone treats a file
another connection is writing as damaged, and a store that rebuilds on damage throws its
data away for waiting too briefly. Only `SQLITE_CORRUPT*` and `SQLITE_NOTADB` (extended
codes masked to the primary) are damage.

### 2. An integrity check needs a fresh connection

`integrity_ok(path, extra=)`. On a long-lived reader, `PRAGMA integrity_check` reported a
malformed FTS5 index after another connection's writes, in 10 of 40 cycles, while a fresh
connection and the writer both said `ok` and the reader's own `MATCH` results were right:
its cached FTS5 structure was stale for the pragma, not for queries. So the check always
opens its own connection. `extra` runs a store's own check (FTS5's `'integrity-check'`)
there too. `unreadable(path)` is the cheap probe for every start: header and schema only.

### 3. A file set aside takes its WAL with it

`set_aside(path)`. A fresh file opened beside an old `-wal` replays someone else's pages.
`-wal` and `-shm` move with the file, to `<name>.corrupt-<UTC stamp>`, kept for a
post-mortem.

### 4. A time column is text, and only fixed width sorts

`to_text(dt)` / `from_text(text, aware=)`. `sqlite3`'s default datetime adapter is
deprecated (Python 3.12) and a value comes back as whatever text went in, so the store
has to pick a format — and range predicates and `ORDER BY` compare text. `to_text` writes
`YYYY-MM-DD HH:MM:SS.ffffff` in UTC (aware values converted, naive taken as UTC), always
four-digit year and six-digit fraction, so text order is time order. Route every bound
datetime through one mapper and every read through `from_text`; a second spelling
anywhere breaks the order silently.

### 5. Immediate, and nested as a savepoint

`transaction(conn, lock=)`. A deferred `BEGIN` that later writes can fail with busy in the
middle of the unit; `BEGIN IMMEDIATE` waits at the start instead. Inside an open
transaction it becomes a savepoint, so a caller can wrap a whole pass around units that
are transactions of their own. `lock` (an `RLock`) is held for the span when threads share
one connection.

## Surface

- `connect(target, *, extensions=None, read_only=False, timeout=10.0) -> sqlite3.Connection`
- `transaction(conn, *, lock=None)` — context manager
- `to_text(datetime) -> str`, `from_text(str, *, aware=False) -> datetime`
- `is_corruption(exc) -> bool`, `unreadable(path) -> bool`, `integrity_ok(path, *, extra=None) -> bool`
- `set_aside(path, *, at=None) -> list[Path]`
- `ExtensionUnavailableError(extension, cause)` — `.extension` names the loader

## Boundary

Imports no consumer app (`a2web`, `a2kay`) — enforced by `tests/test_boundary_sqlite_sidecar.py`.
