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
| `get()` | the record, else `None`: for caches and derivable files |
| `need()` | the record, `None` when absent, `Refused` (names the file) for Torn or ForeignVersion |
| `write(rec)` / `delete()` | atomic replace (indent 1) / remove, idempotent |
| `DocSet(path_of, load=, dump=)` | `of(key) -> Doc`, `keys()` lists the folder (dot-files skipped) |

`load` raises `ValueError` for a bad shape (read as Torn) and `ForeignVersionError(found, want)` for another version.
No msgspec, no version envelope: those stay in the host. Depends on `atomic-io` only.

Not here: task-loop's `FileTickets` (hard-link ticket line) is a lock protocol, not a document.
