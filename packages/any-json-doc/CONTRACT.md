# any-json-doc contract (candidate)

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

- `Doc.read()` returns exactly one of `Present`, `Absent`, `Torn`, `ForeignVersion`. Missing file: `Absent`. Unreadable,
  non-UTF-8, invalid JSON or `load` raising `ValueError`: `Torn`. `load` raising `ForeignVersionError`: `ForeignVersion`.
- `write` replaces atomically: a concurrent reader sees the old document or the new one, never `Torn`.
- `need` raises `Refused` for `Torn`/`ForeignVersion`; `get` maps both to `None`.
- A version is never migrated and never read as empty.

No consumer app is imported. Executable acceptance: `tests/`.
