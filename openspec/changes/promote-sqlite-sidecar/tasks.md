## 1. sqlite-sidecar

- [x] 1.1 Tests lifted from a2kay: parent dir, `:memory:`, WAL, extension failure named, read-only refuses a write; transaction commits/rolls back, nests as a savepoint, holds its lock; the codec's width, padding, round trip and order; corruption vs busy; `unreadable`; `integrity_ok` with `extra`; `set_aside` with `-wal`/`-shm`; a second process reads the last commit while a write is open
- [x] 1.2 `packages/sqlite-sidecar` from a2kay's `services/sqlite_sidecar.py`; boundary test; README "What this package knows"
- [x] 1.3 Catalog entry, a2kay use case, testpath; `make catalog`; `make check` green
- [ ] 1.4 Tag `sqlite-sidecar-v0.1.0` (after review)
