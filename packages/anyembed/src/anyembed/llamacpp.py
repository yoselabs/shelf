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

A loaded model (or vocabulary) is closed at interpreter exit (``atexit``), while ``llama_cpp`` is still
importable. Left to the garbage collector it is freed during module teardown, after the
bindings are gone: ``Llama.__del__`` raises, and on Metal ``ggml_metal_device_free`` then
finds live resource sets and aborts the process (SIGABRT, a non-zero exit after a run that
otherwise succeeded).
"""

from __future__ import annotations

import atexit
import threading
import weakref
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
        self._vocab: Any = None

    @property
    def max_tokens(self) -> int:
        """The longest input, special tokens included, embedded without truncation."""
        return self._max_tokens

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
        atexit.register(_close_at_exit, weakref.ref(self))
        return self._llm

    def _tokenizer(self) -> Any:
        """The loaded model, or else a vocabulary-only load of the same file: counting
        tokens needs no weights and no GPU. Call with the lock held."""
        if self._llm is not None:
            return self._llm
        if self._vocab is None:
            path = self.resolve()
            try:
                loader = self._loader
                if loader is None:
                    from llama_cpp import Llama  # noqa: PLC0415 — heavy, lazy

                    loader = Llama
                self._vocab = loader(model_path=str(path), vocab_only=True, verbose=False)
            except Exception as exc:
                msg = f"GGUF model {self.model_id!r} vocabulary could not be loaded from {path}: {exc}"
                raise AnyEmbedError(msg) from exc
            # Freed at exit like the model: left to module teardown, `Llama.__del__` raises.
            atexit.register(_close_at_exit, weakref.ref(self))
        return self._vocab

    def count_tokens(self, texts: list[str]) -> list[int]:
        """How many tokens each text takes as a document, prefix and special tokens included.

        A count above :attr:`max_tokens` is a text :meth:`embed_documents` would truncate;
        a host that must not lose that text routes it to an embedder with a longer limit.
        """
        with self._lock:
            tok = self._tokenizer()
            return [len(tok.tokenize((self._document_prefix + t).encode("utf-8"), add_bos=True)) for t in texts]

    def close(self) -> None:
        """Free the model (the next call loads it again)."""
        with self._lock:
            llm, self._llm = self._llm, None
            vocab, self._vocab = self._vocab, None
        for handle in (llm, vocab):
            if handle is not None and hasattr(handle, "close"):
                handle.close()

    def _truncate(self, llm: Any, text: str) -> str:
        tokens: list[int] = llm.tokenize(text.encode("utf-8"), add_bos=True)
        if len(tokens) <= self._max_tokens:
            return text
        # `tokens` holds the opening and closing special tokens; keep the content between them.
        kept: bytes = llm.detokenize(tokens[1 : self._max_tokens - 1])
        return kept.decode("utf-8", errors="ignore")

    def _vectors(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with self._lock:
            llm = self._ensure()
            try:
                vectors: list[list[float]] = llm.embed([self._truncate(llm, t) for t in texts], normalize=True)
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


def _close_at_exit(ref: weakref.ref[LlamaCppEmbedder]) -> None:
    embedder = ref()
    if embedder is not None:
        embedder.close()


__all__ = ["LlamaCppEmbedder", "Pooling"]
