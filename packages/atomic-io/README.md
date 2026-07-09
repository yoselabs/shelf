# atomic-io

**Write a text file so a crash or a concurrent reader never sees a partial write.**
Write to a temp file in the *same* directory, flush + `fsync`, then `os.replace` onto
the target. The rename is atomic on POSIX; a failure before the replace leaves any
pre-existing target untouched.

```python
from pathlib import Path
from atomic_io import atomic_write_text

atomic_write_text(Path("notes/index.md"), "# Notes\n")
```

- Creates missing parent directories.
- On any exception before the replace, the temp file is cleaned up and the prior
  target content (if any) survives untouched.

## Boundary

Imports no consumer app (`a2web`, `a2kay`) — enforced by `tests/test_boundary_atomic_io.py`.
