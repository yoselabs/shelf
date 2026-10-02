## Why

A DuckDB file opened after an unclean exit replays its WAL, and the next checkpoint — the shutdown one on a clean close, or an automatic one — persists the ART indexes without the replayed rows (duckdb/duckdb#26106, open; reproduced on 1.5.0–1.5.5). A later DELETE of those rows then fails with `Failed to delete all rows from index` (FATAL on 1.5.x; 1.4.x returns wrong lookups instead). a2kay's graph and search sidecars broke this way twice (2026-07-17, 2026-10-02). An explicit `CHECKPOINT` right after the replay persists the rows correctly.

## What Changes

- `connect()` runs `CHECKPOINT` immediately after opening a file target, so a replayed WAL is folded in by the path that keeps indexes whole. A no-op when there is no WAL; skipped for `:memory:`.
- New `is_index_drift(exc)`: true for the "Failed to delete all rows from index" failure, so a store holding derived state can move the file aside and rebuild instead of crashing.

## Capabilities

### New Capabilities
- `duckdb-sidecar`: the sidecar connection helper's contract (opening, the lock-conflict and index-drift classifiers).

### Modified Capabilities

## Impact

`packages/duckdb-sidecar` (minor version bump, `duckdb-sidecar-v0.3.0`). Every consumer's sidecar stores (a2kay: graph, audit, search, runs) get the checkpoint by upgrading the tag.
