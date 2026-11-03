"""Write a file so a crash never leaves it half-written."""
import os
import tempfile


def atomic_write(path: str, data: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".")
    with os.fdopen(fd, "w") as f:
        f.write(data)
    os.replace(tmp, path)
