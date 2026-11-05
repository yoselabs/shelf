"""The one place a log file is replaced rather than appended to: keep the lines a predicate accepts."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from jsonl_log._append import append_line, open_append

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _filter(raw: bytes, keep: Callable[[bytes], bool]) -> tuple[int, bytes]:
    """(lines dropped, the bytes to keep) of ``raw``; a blank line goes uncounted, a torn last line stays."""
    dropped = 0
    out: list[bytes] = []
    lines = raw.split(b"\n")
    torn = lines.pop()  # b"" when raw ends with a newline
    for line in lines:
        if not line.strip():
            continue
        if keep(line):
            out.append(line + b"\n")
        else:
            dropped += 1
    if torn:
        out.append(torn)
    return dropped, b"".join(out)


def rewrite_file(path: Path, keep: Callable[[bytes], bool], *, then: Callable[[], None]) -> int:
    """Replace ``path`` by its lines ``keep`` accepts, atomically and only if one goes; returns the lines dropped.

    Lines another process appended while this ran are carried over: before the replace, and after it
    from the old file (a writer still holding the old inode). ``then`` runs right after the replace
    (the caller drops its descriptor to the old file).
    """
    try:
        old = path.open("rb")
    except FileNotFoundError:
        return 0
    with old:
        dropped, kept = _filter(old.read(), keep)
        if not dropped:
            return 0
        tmp = path.with_name(path.name + ".rewrite")
        tmp.unlink(missing_ok=True)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        try:
            more, tail = _filter(old.read(), keep)  # appended while the filter ran
            dropped += more
            _ = append_line(fd, kept + tail)
        finally:
            os.close(fd)
        tmp.replace(path)
        then()
        late = old.read()  # written to the old inode in the replace window
        if late:
            more, tail = _filter(late, keep)
            dropped += more
            if tail:
                fd = open_append(path)
                try:
                    _ = append_line(fd, tail)
                finally:
                    os.close(fd)
    return dropped
