"""In-process embedder over a GGUF file through `llama.cpp` (``llama-cpp-python``).

The same model as :class:`~anyembed.local.LocalEmbedder`, quantized: ``bge-m3`` as GGUF
Q8_0 on Metal scores what the `transformers` fp32 model scores (cosine >= 0.999 per
vector) at a quarter of the resident memory, with no torch in the process.

Pooling and normalization are one setting used on both sides: documents and queries go
through the same :meth:`_vectors`, so a query vector and a document vector are always
comparable. ``pooling`` must be the model's own recipe (``cls`` for BGE, ``mean`` for
most sentence-transformers models, ``last`` for decoder embedders).

Truncation is by tokens, as `transformers` truncates: a text longer than ``max_tokens``
keeps its first ``max_tokens - 2`` content tokens, and the model's special tokens are
added back around them.

One ``Llama`` context is not safe to share between threads; calls are serialized by a
lock, so one instance may serve an indexer thread and a query thread at once.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from anyembed.errors import AnyEmbedError

if TYPE_CHECKING:
    from collections.abc import Callable

Pooling = Literal["cls", "mean", "last"]

#: ``llama_pooling_type`` values (llama.h).
_POOLING: dict[str, int] = {"mean": 1, "cls": 2, "last": 3}


class LlamaCppEmbedder:
    """A GGUF embedder on `llama.cpp`, GPU-offloaded where the build supports it (Metal, CUDA)."""

    def __init__(
        self,
        *,
        model_id: str,
        dim: int,
        path: str | Path | None = None,
        repo_id: str | None = None,
        filename: str | None = None,
        pooling: Pooling = "cls",
        query_prefix: str = "",
        document_prefix: str = "",
        max_tokens: int = 512,
        gpu: bool = True,
        offline: bool = True,
        loader: Callable[..., Any] | None = None,
    ) -> None:
        """``path`` names the GGUF file; or ``repo_id`` + ``filename`` find it in the Hugging Face cache.

        ``model_id`` is the identity a host persists beside its vectors: name the quantization
        in it (a Q8_0 vector is not bit-identical to the fp32 model's). ``loader`` replaces
        ``llama_cpp.Llama`` (tests).
        """
        if path is None and (repo_id is None or filename is None):
            msg = "LlamaCppEmbedder needs `path`, or `repo_id` and `filename`"
            raise ValueError(msg)
        if pooling not in _POOLING:
            msg = f"pooling must be one of {sorted(_POOLING)}, not {pooling!r}"
            raise ValueError(msg)
        self.model_id = model_id
        self.dim = dim
        self._path = Path(path) if path is not None else None
        self._repo = (repo_id, filename)
        self._pooling = pooling
        self._query_prefix = query_prefix
        self._document_prefix = document_prefix
        self._max_tokens = max_tokens
        self._gpu = gpu
        self._offline = offline
        self._loader = loader
        self._lock = threading.Lock()
        self._llm: Any = None

    def resolve(self) -> Path:
        """The GGUF file: ``path``, or the cached ``repo_id``/``filename`` (never a download offline)."""
        if self._path is not None:
            if not self._path.is_file():
                msg = f"GGUF model {self.model_id!r} not found at {self._path}"
                raise AnyEmbedError(msg)
            return self._path
        repo_id, filename = self._repo
        try:
            from huggingface_hub import hf_hub_download  # noqa: PLC0415 — only for a repo-named model

            return Path(hf_hub_download(repo_id=str(repo_id), filename=str(filename), local_files_only=self._offline))
        except Exception as exc:
            msg = f"GGUF model {self.model_id!r} ({repo_id}/{filename}) could not be found (offline={self._offline}): {exc}"
            raise AnyEmbedError(msg) from exc

    def _ensure(self) -> Any:
        """Load the model once. Call with the lock held."""
        if self._llm is not None:
            return self._llm
        path = self.resolve()
        try:
            loader = self._loader
            if loader is None:
                from llama_cpp import Llama  # noqa: PLC0415 — heavy, lazy

                loader = Llama
            # One sequence of at most `max_tokens` per decode: on Metal a bigger batch packs
            # several sequences into one KV cache and runs slower, not faster.
            self._llm = loader(
                model_path=str(path),
                embedding=True,
                pooling_type=_POOLING[self._pooling],
                n_gpu_layers=-1 if self._gpu else 0,
                n_ctx=self._max_tokens,
                n_batch=self._max_tokens,
                n_ubatch=self._max_tokens,
                verbose=False,
            )
        except Exception as exc:
            msg = f"GGUF model {self.model_id!r} could not be loaded from {path}: {exc}"
            raise AnyEmbedError(msg) from exc
        return self._llm

    def _truncate(self, llm: Any, text: str) -> str:
        tokens = llm.tokenize(text.encode("utf-8"), add_bos=True)
        if len(tokens) <= self._max_tokens:
            return text
        # `tokens` holds the opening and closing special tokens; keep the content between them.
        return bytes(llm.detokenize(tokens[1 : self._max_tokens - 1])).decode("utf-8", errors="ignore")

    def _vectors(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with self._lock:
            llm = self._ensure()
            try:
                vectors = llm.embed([self._truncate(llm, t) for t in texts], normalize=True)
            except Exception as exc:
                msg = f"GGUF model {self.model_id!r} failed to embed: {exc}"
                raise AnyEmbedError(msg) from exc
        out = [list(map(float, v)) for v in vectors]
        if any(len(v) != self.dim for v in out):
            msg = f"GGUF model {self.model_id!r} returned vectors of {len(out[0])} dims, not {self.dim}"
            raise AnyEmbedError(msg)
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed passages for indexing. Returns one ``dim``-length vector per text."""
        return self._vectors([self._document_prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query (the configured query prefix applied)."""
        return self._vectors([self._query_prefix + text])[0]


__all__ = ["LlamaCppEmbedder", "Pooling"]
