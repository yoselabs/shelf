# any-json-doc contract (candidate)

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

- `Doc.read()` returns exactly one of `Present`, `Absent`, `Torn`, `ForeignVersion`. Missing file: `Absent`. Unreadable,
  non-UTF-8, invalid JSON or `load` raising `ValueError`: `Torn`. `load` raising `ForeignVersionError`: `ForeignVersion`.
- `write` replaces atomically: a concurrent reader sees the old document or the new one, never `Torn`.
- `need` raises `RefusedError` for `Torn`/`ForeignVersion`; `get` maps both to `None`.
- `Torn.why` is a message for a human; callers branch on the state, never on its text.
- `DocSet` is a flat folder with one suffix; keys are plain file stems.
- A version is never migrated and never read as empty.

- `read_rev()` reads bytes once, decodes through the same path as `read`, and returns the state plus
  their SHA-256 hex digest (absent: `''`; unreadable: `Torn` with `''`). Revisions are opaque strings.
- `update(fn, *, expect=None)` exclusively locks `<path>.lock` with `ProcessLock.acquire`, timeout
  10 seconds and `reentrant=False`, then re-reads, transforms and atomically writes, returning the record.
  Absent passes `None` to `fn`; present passes the record, including false-valued records.
- Torn/ForeignVersion raise `RefusedError` before revision comparison or transform. Mismatching `expect`
  raises `Conflict(path, found, expected)` without writing or calling `fn`. Matching revisions proceed.
- Equal bytes = equal state: A->B->A is not a conflict (intended).
- Participating threads and processes cannot lose updates. `write` and `delete` do not acquire the lock.
- Same-thread recursive updates of the same resolved path raise `RuntimeError`. The lock is released
  in `finally`, including transform/write failures. `LockHeldError` propagates on timeout.

Imports: stdlib, `atomic-io` and `process-lock`. Vendoring takes both dependencies along.
No consumer app is imported. Executable acceptance: `tests/`.
