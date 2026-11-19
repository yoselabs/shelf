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


def test_offline_loading_leaves_the_process_environment_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    # offline is an explicit local_files_only argument, never a mutation of os.environ.
    import os  # noqa: PLC0415

    from transformers import AutoModel, AutoTokenizer  # noqa: PLC0415

    seen: dict[str, object] = {}

    def refuse(_name: str, **kwargs: object) -> None:
        seen.update(kwargs)
        msg = "no files"
        raise OSError(msg)

    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", refuse)
    monkeypatch.setattr(AutoModel, "from_pretrained", refuse)
    with pytest.raises(AnyEmbedError):
        LocalEmbedder(model_name="m", dim=8, offline=True).embed_query("x")
    assert seen == {"local_files_only": True}
    assert "HF_HUB_OFFLINE" not in os.environ
    assert "TRANSFORMERS_OFFLINE" not in os.environ
