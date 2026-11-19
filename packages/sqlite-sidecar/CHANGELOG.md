# Changelog

## 0.3.0

- `integrity_ok` no longer folds every `sqlite3.Error` into `False`: `False` means damaged (failed check, corrupt, not a
  database, or `extra` raising); a busy, absent or unreadable file raises. New `timeout` argument (default 5 s, as before).
- New `is_busy(exc)` (result code BUSY or LOCKED, never the message) and `move_aside(path, destination)`, the one
  move of a file with its `-wal`/`-shm`; `set_aside` uses it. Companions now move before the file, so a crash part-way never
  leaves a WAL beside a fresh file. Names unchanged.
- `transaction` rolls back when `COMMIT` itself fails (it used to leave the transaction open).
