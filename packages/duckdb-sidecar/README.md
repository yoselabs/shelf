# duckdb-sidecar

**Stop repeating the DuckDB sidecar-connection dance, and stop rediscovering what
DuckDB does not document.** Per-concern derived-state stores (a graph store, an
audit log, a search index, job history — anything that owns a single writer
connection to its own DuckDB file) all open that connection the same way:
normalize the target, create the parent directory for a file target, support the
`":memory:"` passthrough, then `duckdb.connect`. This is the one place that dance
lives, together with the two hazards a sidecar store meets after it is open.

```python
from pathlib import Path
from duckdb_sidecar import connect, is_lock_conflict, rename_column

conn = connect(Path("vault/.derived/graph.duckdb"))
conn = connect(":memory:")  # in-memory, touches no filesystem path

try:
    conn = connect(target)
except Exception as exc:
    if is_lock_conflict(exc):
        ...  # another process is already writing this file

rename_column(conn, table="edge", old="edge_kind", new="edge_type")
```

Schema, migrations and query surface stay with each store. Deliberately not a
lifecycle base class.

## What this package knows

Four things, none of them in DuckDB's documentation, each learned from a failure.
Two have a code shape here; two are rules about the writer you are about to write.

### 1. A second writer is an `IOException`, same as a missing file

`is_lock_conflict(exc)`. DuckDB reports lock contention as a plain
`duckdb.IOException` — the class it also uses for a missing file, an unreadable
directory, and a corrupt header. The only thing separating it is the substring
`Conflicting lock is held` in the message. So a store that wants to say "another
session already owns this vault" while letting every other IO failure keep its own
real error has no choice but to match a vendor string, and the day an upgrade
rewords it, every consumer matching it privately breaks in silence.

The test that pins it spawns a second interpreter, lets it take the write lock, and
reads the real failure. Building the exception by hand would prove only that the
substring matches itself.

### 2. A secondary index blocks a column rename

`rename_column(conn, table=…, old=…, new=…)`. DuckDB refuses `ALTER TABLE … RENAME
COLUMN` while anything depends on the table, and a secondary index counts:

```
duckdb.DependencyException: Cannot alter entry "node" because there are entries
that depend on it.
```

The message names neither the index nor the column, and a store usually meets it
for the first time on a user's existing database — the one place iteration is not
available. `rename_column` drops every index on the table, renames, and rebuilds
each from the definition DuckDB itself reports, rewriting the renamed column
inside the index's own column list and nowhere else. It returns `False` when there
is nothing to rename — an already-upgraded database, a fresh one built from current
DDL, or a ladder where several old spellings converge on one new name and this is
not the branch that fits — and raises only when the table holds both columns, where
the history is ambiguous and dropping one is not its call.

The ordering rule that follows, and which no helper can enforce for you: **create
new indexes after the renames, not before.** An `ADD COLUMN` plus its index placed
above a rename in the same migration will make that rename fail.

### 3. Upsert churn can corrupt an ART index — write-skip is not an optimization

No code here; it belongs to your writer, and you have to build it. A store whose
upsert does `DELETE` + `INSERT` against a property table for every field on every
write generates enough index churn, on a large corpus, to trip:

```
Failed to delete all rows from index
```

That is a fatal, and it is data corruption, not a slow query. Two consequences:

- **Short-circuit on a content hash.** A row whose content is byte-identical to
  what is stored has nothing to gain from redoing the churn. Compare the path too
  — a rename leaves the content hash untouched and still has to move the row.
- **Do not add a secondary index to make writes or scans faster without measuring
  first.** On a few-thousand-row table DuckDB's optimizer sequential-scans
  regardless, so the index buys nothing, *and* an ART index over a high-cardinality
  text column trips the same fatal under upsert churn. Adding it makes the store
  both no faster and corruptible. The fix for a slow reindex is to touch fewer
  rows, not to index more columns.

### 4. The FTS index is static — rebuilding is O(corpus), not O(change)

Also no code here. `PRAGMA create_fts_index` builds the whole thing; there is no
incremental update, so reflecting one changed row costs a full rebuild — measured
at 3.2s over ~6k documents, rising linearly. It must not run on the write path.

Mark the index stale on write and rebuild once, lazily, on the next lexical read.
**Keep the stale flag as a row in the same DuckDB file**, never in instance state:
a crash between the write and the read would otherwise leave a stale index looking
fresh, and nothing would ever rebuild it.

## Boundary

Imports no consumer app (`a2web`, `a2kay`) — enforced by `tests/test_boundary_duckdb_sidecar.py`.
