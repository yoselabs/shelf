"""LocalEmbedder — the state surface + fail-loud contract (without downloading weights)."""

from __future__ import annotations

import pytest
from anyembed import AnyEmbedError, Embedder, LocalEmbedder


def test_surfaces_model_id_and_dim() -> None:
    emb = LocalEmbedder(model_name="BAAI/bge-small-en-v1.5", dim=384)
    assert emb.model_id == "BAAI/bge-small-en-v1.5"
    assert emb.dim == 384
    # structurally satisfies the Embedder protocol
    assert isinstance(emb, Embedder)


def test_missing_model_fails_loud_offline() -> None:
    # A nonexistent model with offline=True must raise AnyEmbedError, never download.
    emb = LocalEmbedder(model_name="definitely-not/a-real-model-xyz", dim=8, offline=True)
    with pytest.raises(AnyEmbedError):
        emb.embed_query("hello")
