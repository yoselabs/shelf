"""Receipts: a green result remembered under a key, so the same work is never run twice.

The file is `{"version": 1, "receipts": {name: [key, ...]}}`, newest key first, at most `keep` per name. It is plain JSON so a reader in
any language can use it. A missing, unreadable or malformed file remembers nothing (a rerun, never a false pass); the next `record`
writes a clean one. The file is replaced whole and atomically, so a reader never sees half of it; two writers at once may lose one record.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from atomic_io import atomic_write_json
from content_digest import digest

if TYPE_CHECKING:
    from pathlib import Path

VERSION = 1
KEY_LENGTH = 32


def key(**parts: object) -> str:
    """The key of what a result depends on: 32 hex of the canonical hash of `parts`, whatever their order.

    Raises `TypeError` or `ValueError` for a part JSON cannot say (a datetime, a set, bytes): a key must never hide a difference.
    """
    return digest(parts, length=KEY_LENGTH)


class Receipts:
    """The ledger of green results at `path`: `has(name, key)` before running, `record(name, key)` after it passed."""

    def __init__(self, path: Path, *, keep: int = 50) -> None:
        self._path = path
        self._keep = keep

    def has(self, name: str, key: str) -> bool:
        """Whether a result named `name` passed under `key`."""
        return key in self._read().get(name, [])

    def record(self, name: str, key: str) -> None:
        """Remember that `name` passed under `key`; the oldest keys of `name` beyond `keep` are forgotten."""
        receipts = self._read()
        receipts[name] = [key, *(k for k in receipts.get(name, []) if k != key)][: self._keep]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._path, {"version": VERSION, "receipts": receipts}, indent=1, sort_keys=True)

    def _read(self) -> dict[str, list[str]]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        receipts = data.get("receipts") if isinstance(data, dict) else None
        if not isinstance(receipts, dict):
            return {}
        return {
            name: [k for k in keys if isinstance(k, str)]
            for name, keys in receipts.items()
            if isinstance(name, str) and isinstance(keys, list)
        }
