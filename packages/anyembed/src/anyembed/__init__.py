"""anyembed — stop caring which embedding backend is underneath.

A neutral :class:`Embedder` interface plus an in-process :class:`LocalEmbedder`
(the BGE `transformers` recipe). Compute (``embed_documents`` / ``embed_query``) is
hidden and swappable; the state — ``(model_id, dim)`` — is surfaced so a host can
rebuild its vector index on a model/dim change rather than silently mixing
incompatible vectors. Failures raise :class:`AnyEmbedError`; the host translates it
into its own error type at the seam.
"""

from __future__ import annotations

from anyembed.base import Embedder
from anyembed.errors import AnyEmbedError
from anyembed.local import LocalEmbedder

__all__ = ["AnyEmbedError", "Embedder", "LocalEmbedder"]
