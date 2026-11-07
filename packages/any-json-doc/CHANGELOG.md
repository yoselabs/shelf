# any-json-doc — changelog

- 0.2.0: `Doc.read_rev() -> tuple[Read[T], str]`; `Doc.update(fn, *, expect=None) -> T` with process/thread locking and optimistic revisions; `Conflict(path, found, expected)`; depends on `process-lock>=0.2,<1`.
