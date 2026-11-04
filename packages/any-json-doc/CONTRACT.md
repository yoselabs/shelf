# any-json-doc contract (candidate)

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

- `Doc.read()` returns exactly one of `Present`, `Absent`, `Torn`, `ForeignVersion`. Missing file: `Absent`. Unreadable,
  non-UTF-8, invalid JSON or `load` raising `ValueError`: `Torn`. `load` raising `ForeignVersionError`: `ForeignVersion`.
- `write` replaces atomically: a concurrent reader sees the old document or the new one, never `Torn`.
- `need` raises `RefusedError` for `Torn`/`ForeignVersion`; `get` maps both to `None`.
- `Torn.why` is a message for a human; callers branch on the state, never on its text.
- `DocSet` is a flat folder with one suffix; keys are plain file stems.
- A version is never migrated and never read as empty.

Imports: stdlib and `atomic-io`. A repo vendoring this package vendors `atomic-io` with it.
No consumer app is imported. Executable acceptance: `tests/`.
