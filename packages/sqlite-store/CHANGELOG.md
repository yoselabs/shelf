# Changelog

## 0.1.0

- Extract task-loop's generic SQLite file lifecycle into `Schema`, `Store`,
  `open_rw` and `open_ro`, with WAL, filesystem refusal and integrity caching.
- Reusable per-thread/process/file writers, immediate transactions, change counters,
  atomic ordered upgrades, explicit serialized quarantine and revision-guarded updates.
- Plain pytest contract tests; stdlib only, POSIX only, Python 3.12+.
