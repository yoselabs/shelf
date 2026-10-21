"""In-process local embedder via `transformers` — the BGE recipe (the ``[transformers]`` extra).

CLS-token pooling + L2-normalize (the BGE recipe). Documents embed raw; queries
get the configured instruction prefix. Loads once, lazily. By default it never
reaches the network (``offline=True``): the weights are expected to be a baked,
on-disk asset, and a missing model fails loud (``AnyEmbedError``) rather than
triggering a download in the request path. Without the extra installed, the first embed
raises ``AnyEmbedError`` naming it; constructing one needs nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from anyembed.errors import AnyEmbedError

if TYPE_CHECKING:
    import numpy as np


class LocalEmbedder:
    """A local `transformers` embedder, parameterized by model + dim + query prefix."""

    def __init__(
        self,
        *,
        model_name: str,
        dim: int,
        query_prefix: str = "",
        batch: int = 64,
        max_tokens: int = 512,
        offline: bool = True,
    ) -> None:
        self.model_id = model_name
        self.dim = dim
        self._query_prefix = query_prefix
        self._batch = batch
        self._max_tokens = max_tokens
        self._offline = offline
        self._tokenizer = None
        self._model = None

    def _ensure_model(self) -> None:
        """Lazily load the tokenizer + model once. Fail loud if unavailable."""
        if self._model is not None:
            return
        if self._offline:
            import os  # noqa: PLC0415 — set offline env before transformers loads

            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        try:
            import torch  # noqa: F401, PLC0415 — heavy, lazy; _encode uses it
            from transformers import AutoModel, AutoTokenizer  # noqa: PLC0415 — heavy, lazy
        except ImportError as exc:
            msg = f"LocalEmbedder needs torch and transformers, which are not installed: install anyembed[transformers] ({exc})"
            raise AnyEmbedError(msg) from exc
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            self._model = AutoModel.from_pretrained(self.model_id)
            self._model.eval()
        except Exception as exc:
            msg = f"embedding model {self.model_id!r} could not be loaded (offline={self._offline}): {exc}"
            raise AnyEmbedError(msg) from exc

    def _encode(self, texts: list[str]) -> np.ndarray:
        self._ensure_model()
        import numpy as np  # noqa: PLC0415
        import torch  # noqa: PLC0415 — present: _ensure_model checked it

        tok, model = self._tokenizer, self._model
        if tok is None or model is None:  # pragma: no cover -- _ensure_model guarantees load
            msg = "tokenizer/model not initialised after _ensure_model()"
            raise AnyEmbedError(msg)
        out: list[np.ndarray] = []
        with torch.no_grad():
            for i in range(0, len(texts), self._batch):
                batch = texts[i : i + self._batch]
                enc = tok(batch, padding=True, truncation=True, max_length=self._max_tokens, return_tensors="pt")
                hidden = model(**enc).last_hidden_state[:, 0]  # CLS token (BGE recipe)
                hidden = torch.nn.functional.normalize(hidden, p=2, dim=1)
                out.append(hidden.cpu().numpy().astype("float32"))
        if not out:
            return np.zeros((0, self.dim), dtype="float32")
        return np.vstack(out)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed passages for indexing. Returns one ``dim``-length vector per text."""
        return [row.tolist() for row in self._encode(texts)]

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query (the configured instruction prefix applied)."""
        return self._encode([self._query_prefix + text])[0].tolist()


__all__ = ["LocalEmbedder"]
