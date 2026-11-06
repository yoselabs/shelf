# Changelog

## Unreleased

- A read-only open of an empty, version-0 file (a writer is creating it) returns None like a missing file instead of
  raising `SchemaError`; a non-empty version-0 file still raises.

## 0.1.0

- Evict dead threads' shared writers on every request and register process-exit
  cleanup and fork handling once through a weak registry of connection caches.
- Cover quarantine/recreation across spawned processes, thread churn, atexit
  checkpointing and WAL/SHM cleanup on the last shared close with plain pytest.
- Record the promotion delivery and document the import-time POSIX requirement.
- Extract task-loop's generic SQLite file lifecycle into `Schema`, `Store`,
  `open_rw` and `open_ro`, with WAL, filesystem refusal and integrity caching.
- Reusable per-thread/process/file writers, immediate transactions, change counters,
  atomic ordered upgrades, explicit serialized quarantine and revision-guarded updates.
- Plain pytest contract tests; stdlib only, POSIX only, Python 3.12+.
