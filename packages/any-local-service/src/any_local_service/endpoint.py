"""Publish the bound URL atomically for exactly its serving lifetime."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from atomic_io import atomic_write_text

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@contextlib.contextmanager
def published_endpoint(path: Path, url: str) -> Generator[None]:
    """Write the bound URL; remove it even when the body raises."""
    atomic_write_text(path, url)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
