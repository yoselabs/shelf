"""Embedder protocol — the neutral surface, with the state boundary surfaced.

The design law for an "any-*" library: hide the compute, surface the state. Here
compute is ``embed_documents`` / ``embed_query`` (clean, swappable); the state is
``(model_id, dim)`` — surfaced so a host can detect a model/dim change and rebuild
its vector index rather than silently mixing incompatible vectors.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    """A text embedder. Fail loud (raise ``AnyEmbedError``), never silently degrade."""

    #: Stable identity of the model — persist it; a change means the index is stale.
    model_id: str
    #: Vector dimension — the index schema depends on it; a change means rebuild.
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed passages for indexing — one ``dim``-length vector per text."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single search query — one ``dim``-length vector."""
        ...


__all__ = ["Embedder"]
