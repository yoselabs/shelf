## Context

a2kay's `services/sqlite_sidecar.py` (sqlite-graph-and-logs D1) serves four stores: search
(two connections, `sqlite-vec` loaded), graph (one connection, read-only opens from a second
process), audit and run history (append-only, UTC times). `duckdb-sidecar` is the precedent
for shape and boundary.

## Goals / Non-Goals

**Goals:** one open and one transaction for every SQLite sidecar; the failure tests a consumer
cannot get right by reading the docs.
**Non-Goals:** schema, migrations or queries (each store's); an async wrapper (`sqlite-resource`
is that, over `aiosqlite`); a lifecycle base class.

## Decisions

- **Functions over `sqlite3.Connection`, like `duckdb-sidecar`.** The consumer holds the stdlib
  connection; nothing here holds state worth a type. `transaction` is a context manager.
- **`sqlite-resource` is not evolved.** It is async (`aiosqlite`), lazy, one connection, no
  extension load; three of a2kay's stores need sync access and one needs two connections and an
  extension. Evolving it would serve two masters; the two stay siblings.
- **Extensions are a name → loader map**, so the failure names what failed
  (`ExtensionUnavailableError.extension`) and the consumer keeps its own error type.
- **The timestamp codec writes UTC, fixed width; naive is UTC.** The only format whose text order
  is time order without a collation; `from_text(aware=True)` for logs, naive for indexes that
  store naive UTC on purpose.
- **`set_aside` moves `-wal`/`-shm` but no mark file.** A "rebuild on next start" mark is a
  consumer's policy.

## Risks / Trade-offs

- [A consumer writes a datetime without `to_text`] → its order breaks silently; the README says
  route every bound datetime through one mapper.
- [`read_only` on a WAL file needs the `-shm` writable or present] → the normal case for a second
  process beside a live writer; documented by the two-process test.
