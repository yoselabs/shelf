"""An append-only JSON-lines log, rotated by size, read back newest file first.

- **Writes.** One ``write`` + ``flush`` per line, no ``fsync``. The size is counted in
  process, seeded by one ``tell`` at open. The file is opened in append mode only.
- **Rotation.** Before an append would take the file past ``rotate_bytes``, the files shift
  (``.{keep-2}`` → ``.{keep-1}``, the oldest dropped, …, the file → ``.1``), so at most
  ``keep`` files exist. A line is never split across files.
- **Reads.** A missing file reads empty; a blank line, or one the caller's ``decode``
  refuses with ``ValueError``, is skipped.

The log is codec-agnostic: it moves bytes lines; what a line means is the caller's.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Self, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from io import BufferedWriter

_T = TypeVar("_T")

#: The default size a file may reach before the next append rotates it: 5 MiB.
ROTATE_BYTES = 5 * 1024 * 1024

#: The default number of files kept: the log and ``.1`` … ``.4``.
KEEP = 5


class JsonlLogError(Exception):
    """A refusal of the log."""


class LogClosedError(JsonlLogError):
    """An append to a log that was closed."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"the log {path} is closed")


class LineError(JsonlLogError):
    """A line that holds a newline before its end: it would become two lines."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"a line for {path} holds a newline before its end")


def read_lines(path: Path) -> Iterator[bytes]:
    """The non-blank lines of one file, without their newlines; a missing file has none."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return
    for line in raw.splitlines():
        if line.strip():
            yield line


def read(path: Path, decode: Callable[[bytes], _T]) -> Iterator[_T]:
    """Every line of one file that ``decode`` accepts; a line it refuses with ``ValueError`` is skipped."""
    for line in read_lines(path):
        with contextlib.suppress(ValueError):
            yield decode(line)


class JsonlLog:
    """One rotated JSON-lines log. Append-only at the application level."""

    def __init__(self, path: Path, *, rotate_bytes: int = ROTATE_BYTES, keep: int = KEEP, read_only: bool = False) -> None:
        if keep < 1:
            msg = f"keep must be at least 1, got {keep}"
            raise ValueError(msg)
        self._path = path
        self._rotate_bytes = rotate_bytes
        self._keep = keep
        self._read_only = read_only
        self._file: BufferedWriter | None = None
        self._size = 0
        self._closed = False

    @classmethod
    def open(cls, path: Path | str, *, rotate_bytes: int = ROTATE_BYTES, keep: int = KEEP, read_only: bool = False) -> JsonlLog:
        """The log at ``path``, opened for appending unless ``read_only``."""
        log = cls(Path(path), rotate_bytes=rotate_bytes, keep=keep, read_only=read_only)
        if not read_only:
            _ = log._open_current()
        return log

    @property
    def path(self) -> Path:
        return self._path

    @property
    def read_only(self) -> bool:
        return self._read_only

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._close_file()
        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def append(self, line: bytes) -> bool:
        """Write one line and flush it; ``False`` (nothing written) on a read-only log.

        A missing trailing newline is added. Raises :class:`LogClosedError` once closed and
        :class:`LineError` for a newline before the end.
        """
        if self._closed:
            raise LogClosedError(self._path)
        if self._read_only:
            return False
        data = line if line.endswith(b"\n") else line + b"\n"
        if b"\n" in data[:-1]:
            raise LineError(self._path)
        if self._size and self._size + len(data) > self._rotate_bytes:
            self._rotate()
        file = self._file or self._open_current()
        file.write(data)
        file.flush()
        self._size += len(data)
        return True

    def append_json(self, value: object) -> bool:
        """:meth:`append` of ``value`` as compact JSON."""
        return self.append(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode())

    def files(self) -> list[Path]:
        """Every file the log may hold, newest first: the log, then ``.1`` … ``.{keep-1}``."""
        return [self._path, *(self._rotated(n) for n in range(1, self._keep))]

    def records(self, decode: Callable[[bytes], _T]) -> Iterator[_T]:
        """:func:`read` over every file, newest file first, each file in written order."""
        for path in self.files():
            yield from read(path, decode)

    def _rotated(self, n: int) -> Path:
        return self._path.with_name(f"{self._path.name}.{n}")

    def _open_current(self) -> BufferedWriter:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._path.open("ab")
        self._size = self._file.tell()
        return self._file

    def _close_file(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def _rotate(self) -> None:
        self._close_file()
        if self._keep == 1:
            self._path.unlink(missing_ok=True)
        else:
            for n in range(self._keep - 1, 1, -1):
                with contextlib.suppress(FileNotFoundError):
                    self._rotated(n - 1).replace(self._rotated(n))
            with contextlib.suppress(FileNotFoundError):
                self._path.replace(self._rotated(1))
        self._size = 0


__all__ = ["KEEP", "ROTATE_BYTES", "JsonlLog", "JsonlLogError", "LineError", "LogClosedError", "read", "read_lines"]
