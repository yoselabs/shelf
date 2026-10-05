## Why

a2kay moved its last DuckDB stores (graph, audit log, run history) to SQLite, after its search
index. Four SQLite sidecar files now open the same way and meet the same failures, and the
code that does it is generic: the WAL/autocommit/extension open, an immediate transaction that
nests as a savepoint, a fixed-width timestamp codec, and the tests that tell a damaged file from
a busy one. Each piece was learned from a failure, not from the docs (an FTS5 integrity check
that lied on a long-lived connection, a busy error caught as corruption, a time column that
stopped sorting). Shape-proven by four consumers with two lifecycles — derived indexes that set
aside and rebuild, logs that never do — so it promotes now, beside `duckdb-sidecar`.

## What Changes

- New package `sqlite-sidecar` (stdlib only, born `candidate`): `connect`, `transaction`,
  `to_text`/`from_text`, `is_corruption`, `unreadable`, `integrity_ok`, `set_aside`,
  `ExtensionUnavailableError`. Lifted from a2kay's `services/sqlite_sidecar.py`.
- Catalog entry and a2kay's use case.

## Capabilities

### New Capabilities
- `sqlite-sidecar`: how a sidecar store opens and transacts on its SQLite file, codes a time,
  and tells damage from busy.

### Modified Capabilities

## Impact

`packages/sqlite-sidecar` (`sqlite-sidecar-v0.1.0`). a2kay repoints its four stores from its
local module to the tag and deletes the local copy.
