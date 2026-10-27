# atomic-io

**Write a file (bytes, text or JSON) so a crash or a concurrent reader never sees a partial write.**
Write to a temp file in the *same* directory, flush + `fsync`, then `os.replace` onto
the target. The rename is atomic on POSIX; a failure before the replace leaves any
pre-existing target untouched.

```python
from pathlib import Path
from atomic_io import atomic_write_bytes, atomic_write_json, atomic_write_text

atomic_write_text(Path("notes/index.md"), "# Notes\n")
atomic_write_bytes(Path("blob.bin"), b"\x00\x01")
atomic_write_json(Path("state.json"), {"n": 1}, indent=2, sort_keys=True)  # + one trailing newline
atomic_write_json(Path("cache.json"), {"n": 1}, fsync=False)               # atomic swap, no durability
atomic_write_json(Path("settings.json"), {}, keep_mode=True)               # permissions of the replaced file
```

- `fsync=True` (default) flushes the temp file to disk before the swap; `False` keeps the
  atomic swap only, for state rewritten often.
- `keep_mode=False` (default) leaves the temp file's `0o600`; `True` copies the permission
  bits of the file replaced (the process default, `0o666` minus the umask, when there is none).
- JSON is UTF-8 with no `\u` escapes; an unencodable value raises `TypeError` before the
  target is touched.

- Creates missing parent directories.
- On any exception before the replace, the temp file is cleaned up and the prior
  target content (if any) survives untouched.

## Boundary

Imports no consumer app (`a2web`, `a2kay`) — enforced by `tests/test_boundary_atomic_io.py`.
