"""Write a file so a crash never leaves it half-written."""

import os
import pathlib
import tempfile


def atomic_write(path: str, data: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".")
    with os.fdopen(fd, "w") as f:
        f.write(data)
    pathlib.Path(tmp).replace(path)
