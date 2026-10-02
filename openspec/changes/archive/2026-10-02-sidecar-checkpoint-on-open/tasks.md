## 1. duckdb-sidecar

- [x] 1.1 Failing test: a WAL-only insert into an indexed table, writer killed, reopened through `connect()` and closed, reopened — index lookup and `DELETE FROM` succeed. Verify it fails without the fix.
- [x] 1.2 `connect()` checkpoints a file target after opening. Verify 1.1 passes and the `:memory:` test still passes.
- [x] 1.3 `is_index_drift(exc)` with tests for the drift error, a lock conflict and a non-DuckDB exception.
- [x] 1.4 README "What this package knows": the WAL-replay hazard and both helpers; version 0.3.0. Verify `make check` green, then tag `duckdb-sidecar-v0.3.0`.
