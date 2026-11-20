"""A directory of files as a `Store[str]`: one file per key, written atomically, the key hashed to a safe filename."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from atomic_io import atomic_write_text
from content_digest import digest_bytes

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["FileStore"]

_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")
_PREFIX_MAX = 32


class FileStore:
    """Keeps each `put` value in its own file under `directory`; a `get` of a key never put is None.

    The filename is a readable prefix of the key (letters, digits, `_`, `-`) plus the sha256 of the whole key, so any key
    (slashes, `..`, unicode, thousands of characters) maps to one short name inside `directory` and two keys never share a file.
    The directory is created on the first `put`. The empty string is a value, not a miss.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, key: str) -> Path:
        prefix = _UNSAFE.sub("_", key)[:_PREFIX_MAX].strip("_")
        digest = digest_bytes(key.encode("utf-8", "surrogatepass"), length=64)
        return self.directory / (f"{prefix}-{digest}.txt" if prefix else f"{digest}.txt")

    async def get(self, key: str) -> str | None:
        return await asyncio.to_thread(self._read, self.path_for(key))

    async def put(self, key: str, value: str) -> None:
        await asyncio.to_thread(atomic_write_text, self.path_for(key), value)

    @staticmethod
    def _read(path: Path) -> str | None:
        try:
            return path.read_bytes().decode("utf-8")  # bytes, so a lone \r is not turned into \n
        except FileNotFoundError:
            return None
