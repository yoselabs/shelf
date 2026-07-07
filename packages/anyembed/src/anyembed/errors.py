"""anyembed's own error type — no dependency on any host's error taxonomy."""

from __future__ import annotations


class AnyEmbedError(Exception):
    """An embedder could not load or run (e.g. model weights missing offline)."""


__all__ = ["AnyEmbedError"]
