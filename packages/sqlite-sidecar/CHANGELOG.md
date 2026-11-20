# Changelog

## 0.4.0

- breaking: `connect(..., read_only=)` removed, new `connect_read_only(target, *, extensions=None, timeout=10.0)` (`mode=ro`, creates nothing, no WAL pragmas; the old `read_only=True`); `from_text(text, *, aware=)` is `from_text(text)` (naive UTC) plus new `from_text_utc(text)`.

## 0.3.0

- `integrity_ok` no longer folds every `sqlite3.Error` into `False`: `False` means damaged (failed check, corrupt, not a
  database, or `extra` raising); a busy, absent or unreadable file raises. New `timeout` argument (default 5 s, as before).
- New `is_busy(exc)` (result code BUSY or LOCKED, never the message) and `move_aside(path, destination)`, the one
  move of a file with its `-wal`/`-shm`; `set_aside` uses it. Companions now move before the file, so a crash part-way never
  leaves a WAL beside a fresh file. Names unchanged.
- `transaction` rolls back when `COMMIT` itself fails (it used to leave the transaction open).
