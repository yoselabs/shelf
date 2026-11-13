# sqlite-store

SQLite-on-disk lifecycle glue extracted from task-loop's factory database. Stdlib only,
POSIX only, Python 3.12+. Applications supply their schema and SQL. This is not an ORM
or a query builder: it owns connection safety and transactions, never domain tables.

`quarantine.py` imports `fcntl` at module level, so the package does not import on
Windows. A Windows port would need a different lock.

```python
from pathlib import Path
from sqlite_store import Schema, Store, change_counter
schema = Schema(
    version=1,
    ddl="""
        CREATE TABLE note (
            id TEXT PRIMARY KEY,
            body TEXT NOT NULL,
            rev INTEGER NOT NULL DEFAULT 0
        );
    """,
    steps={},
    name="notes",
    revisioned=frozenset({"note"}),
)
store = Store(schema)
path = Path("notes.db")  # the parent directory must already exist
con = store.shared_rw(path)
if con is None:
    raise RuntimeError("notes storage unavailable")
try:
    with store.begin_immediate(con):
        con.execute("INSERT OR IGNORE INTO note VALUES (?, ?, 0)", ("n", "draft"))
        changed = store.cas_update(con, "note", "id", "n", 0, body="published")
    reader = store.open_ro(path)
    if reader is not None:
        before = change_counter(reader)
        reader.close()
finally:
    store.close_shared()
```

Guarantees:

- Writer opens require WAL, autocommit (`isolation_level=None`), `synchronous=NORMAL`,
  foreign keys and a 5000 ms busy timeout. Journal-mode locking is retried within
  that same five-second window. Read-only opens require existing WAL storage.
- `open_rw(path, schema)` / `open_ro(path, schema)` return caller-owned stdlib connections.
  Close them explicitly; SQLite's connection context manager does not close connections.
  `Store(schema)` additionally owns reusable writers and its own integrity-check cache.
- Shared writers are reused only within the same process, thread, resolved path and
  device/inode identity, while idle and open. `close_shared()` closes this process's
  writers across threads after their operations stop. Forked children replace the
  cache lock and cannot reuse parent connections; thread identifier reuse also cannot
  transfer ownership to a new thread.
  Each shared-writer request closes cached connections belonging to dead threads.
  Process exit closes remaining writers through one module-level atexit callback;
  closing the last connection lets SQLite checkpoint and remove WAL/SHM sidecars.
- `begin_immediate(con)` commits on success and rolls back on any `BaseException`.
  `Store.begin_immediate` also discards shared writers after `sqlite3.DatabaseError`,
  including failures to begin or commit. Transactions do not nest.
- Creation splits DDL on `;` and executes each statement inside one writer transaction.
  **DDL must contain no triggers or embedded semicolons.** It sets `user_version`
  only after all statements succeed. A nonempty unversioned database is refused.
- `upgrade(con, steps, current, target, name="database")` rereads `user_version`
  after obtaining the writer lock. Steps are keyed by starting version and run in
  order in one transaction, including DDL and version changes. A step must not call
  `executescript`, `commit` or `rollback`. A missing or failing step raises `SchemaError`
  and rolls back the entire chain. Writers upgrade older versioned files in place;
  readers refuse older versions. Both refuse newer versions by the schema's name.
- Only explicitly listed, older `quarantine_versions` are retired by writers. A
  `<path>.schema.lock` flock serializes the version recheck so racing openers retire
  the old file once. The old database and existing `-wal`/`-shm` files move to
  `<name>.bad-<time_ns>` before recreation. Use this only for disposable derived
  schemas with their writers stopped. `quarantine(path)` exposes the move itself
  and returns the archive path; direct callers supply their own coordination.
- `PRAGMA quick_check` runs on creation or the first writable open of each resolved
  file identity per process and cache owner. Read-only opens never check integrity.
- `Schema.read_from` (optional) is the oldest version a read-only open accepts; read-only opens never upgrade.
  Optional `Schema.checks` are additional SQL queries with the same exact result
  contract: `[("ok",)]`. Failed checks are never cached. In-place damage after a
  successful check is left to SQLite's ordinary error handling.
- Network/FUSE filesystems and probe failures are refused before connecting. Linux
  uses the deepest `/proc/mounts` entry. Unknown filesystem types are accepted only
  when there is no mounted ancestor below root; network-backed roots cannot be
  detected portably. Mount verdicts are cached per process; call
  `clear_filesystem_cache()` when mounts change. Fork clears these verdicts.
- Unavailable storage, including WAL refusal (`DatabaseError("WAL unavailable")`
  internally), returns `None`. `SchemaError` is always re-raised.
- `cas_update` quotes identifiers, binds values, requires a caller-owned transaction
  and a declared revisioned table, and refuses updates to `rev` or the key column.
  It increments `rev` exactly once on a match and returns `False` on a conflict.
  Standalone `cas_update` takes `revisioned=`; the Store supplies its schema's set.
- `change_counter` exposes `PRAGMA data_version`: compare successive values on the
  same open connection to observe other connections' commits.

All schema DDL, migration SQL, revisioned table names and application queries stay
with the consumer. There is no testing extra or runtime dependency.

## Direction

This package is the seed of a database library, and it will grow into an ORM-shaped one. It is not one yet.

Rules for growth, so it never grows by shortcut:
- Absorb, do not invent. Each addition is a pattern a real caller needed twice (a second slice or a second app). The README names the pattern and the problem it removes.
- Explicit SQL stays first-class. Guarded writes (`cas_update`, UPDATE ... WHERE the precondition still holds) are the safety mechanism and are never hidden behind magic.
- Typed in, typed out. Rows map to models (pydantic v2) through one helper; no tuple indexing in callers.
- Transactions are values (`Tx`) passed by the caller; one writer at a time, so transactions stay short and never wrap external calls.
- Backends later. SQLite stays the only backend until a second is real; every addition names its backend-specific part so another database can follow.
- No dual readers, no compatibility layers: a schema change is a version bump and a drain (see the schema-upgrade rule).
Open: whether factory.db may ever become a golden source (today it is disposable by the 2026-11-08 rule).
