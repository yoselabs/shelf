"""Test double: an :class:`~anyembed.Embedder` that loads no model.

A vector is a hash of its text, normalised to unit length: the same text always lands in the
same place, two texts almost never do, and nothing is downloaded. A search over it runs end to
end and ranks exact repeats first; it says nothing about meaning.
"""

from __future__ import annotations

import hashlib
import math

__all__ = ["HashEmbedder", "hash_vector"]


def hash_vector(text: str, dim: int) -> list[float]:
    """A ``dim``-length unit vector that depends only on ``text``."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    raw = [digest[i % len(digest)] - 127.5 for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


class HashEmbedder:
    """An :class:`~anyembed.Embedder` over :func:`hash_vector`."""

    def __init__(self, dim: int = 384, model_id: str = "hash") -> None:
        self.dim = dim
        self.model_id = model_id

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [hash_vector(text, self.dim) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return hash_vector(text, self.dim)
