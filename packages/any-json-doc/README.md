# any-json-doc

Stop re-writing the one-JSON-file store. A document is replaced atomically (via `atomic-io`) and read as one of four
states, so a half-written file or another install's schema is never mistaken for "nothing there".

```python
from pathlib import Path
from any_json_doc import Absent, Doc, ForeignVersionError, Present

def load(data):  # the host's codec: JSON value -> record
    if data.get("v") != 2:
        raise ForeignVersionError(data.get("v"), 2)
    return data

doc = Doc(Path("pin.json"), load)
assert doc.read() == Absent()
doc.write({"v": 2, "sha": "abc"})
assert doc.read() == Present({"v": 2, "sha": "abc"})
```

| call | job |
|---|---|
| `Doc(path, load=, dump=, *, fsync=False)` | one document; `load`/`dump` default to raw JSON |
| `read()` | `Present(rec)`, `Absent()`, `Torn(path, why)` or `ForeignVersion(path, found, want)` |
| `read_rev()` | `(Read, revision)` from one byte read; SHA-256 hex, or `''` when absent |
| `update(fn, *, expect=None)` | lock, re-read, compare optional revision, apply `fn(record_or_none)`, atomically write and return the record |
| `get()` | the record, else `None`: for caches and derivable files |
| `need()` | the record, `None` when absent, `RefusedError` (names the file) for Torn or ForeignVersion |
| `write(rec)` / `delete()` | atomic replace (indent 1) / remove, idempotent |
| `DocSet(folder, suffix=".json", load=, dump=)` | `of(key) -> Doc` for `folder/key+suffix`, `keys()` lists that flat folder (dot-files skipped) |

`load` raises `ValueError` for a bad shape (read as Torn) and `ForeignVersionError(found, want)` for another version.
No msgspec, no version envelope: those stay in the host. Depends on `atomic-io` and `process-lock` (stdlib otherwise). Vendoring into a repo that copies shelf packages byte-for-byte takes
both dependencies along with it; this package is not stdlib-only on its own.

Not here: task-loop's `FileTickets` (hard-link ticket line) is a lock protocol, not a document.

`update` serializes participating writers with an exclusive `<path>.lock` lock (10-second timeout).
`Torn` and `ForeignVersion` raise `RefusedError` before calling the transform. A stale `expect` raises
`ConflictError` carrying `path`, `found`, and `expected`, leaving the file unchanged. Lock timeouts propagate
`process_lock.LockHeldError`. Recursive updates of the same path in one thread raise `RuntimeError`.
The lock is released even when the transform or write raises. `write` and `delete` remain unlocked.

Revisions are opaque strings: equal bytes = equal state, so A->B->A is not a conflict (intended).
Unreadable files return `Torn` with revision `''`; updates refuse them regardless of `expect`.

```python
state, revision = doc.read_rev()
updated = doc.update(lambda current: {**(current or {}), "sha": "def"}, expect=revision)
```
