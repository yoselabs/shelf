"""Atomic text write — write to a temp file in the same directory, fsync, os.replace.

The rename is atomic on POSIX, so a crash or a concurrent reader never observes a
partially-written or truncated file, and a failure before the replace leaves any
pre-existing target untouched.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically write ``text`` to ``path`` (tempfile + fsync + ``os.replace``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


__all__ = ["atomic_write_text"]
