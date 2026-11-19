# any-json-doc — changelog

- 0.3.0: depends on `content-digest>=0.2,<1`; `read_rev` revision is `digest_bytes(raw, length=64)`, the same sha256 hex as before (no stored revision changes)

- 0.2.0: `Doc.read_rev() -> tuple[Read[T], str]`; `Doc.update(fn, *, expect=None) -> T` with process/thread locking and optimistic revisions; `ConflictError(path, found, expected)`; depends on `process-lock>=0.2,<1`.
