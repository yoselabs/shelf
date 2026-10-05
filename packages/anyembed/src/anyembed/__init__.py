"""anyembed — stop caring which embedding backend is underneath.

A neutral :class:`Embedder` interface, two in-process backends — :class:`LocalEmbedder`
(the BGE `transformers` recipe) and :class:`LlamaCppEmbedder` (a GGUF file on `llama.cpp`,
the ``[llamacpp]`` extra) — and :class:`EmbeddingCache`, vectors kept by
``(model_id, text)`` across index rebuilds. Compute (``embed_documents`` / ``embed_query``) is
hidden and swappable; the state — ``(model_id, dim)`` — is surfaced so a host can
rebuild its vector index on a model/dim change rather than silently mixing
incompatible vectors. Failures raise :class:`AnyEmbedError`; the host translates it
into its own error type at the seam.
"""

from __future__ import annotations

from anyembed.base import Embedder
from anyembed.cache import EmbeddingCache
from anyembed.errors import AnyEmbedError
from anyembed.llamacpp import LlamaCppEmbedder
from anyembed.local import LocalEmbedder

__all__ = ["AnyEmbedError", "Embedder", "EmbeddingCache", "LlamaCppEmbedder", "LocalEmbedder"]
