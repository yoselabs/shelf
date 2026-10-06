"""LlamaCppEmbedder — the state surface, one pooling for both sides, token truncation, fail-loud."""

from __future__ import annotations

import math
import subprocess
import sys
import threading
from typing import TYPE_CHECKING, Any, ClassVar

import pytest
from anyembed import AnyEmbedError, Embedder, LlamaCppEmbedder

if TYPE_CHECKING:
    from pathlib import Path


class _FakeLlama:
    """Stands in for ``llama_cpp.Llama``: one token per word, wrapped in two special tokens."""

    made: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, **kwargs: Any) -> None:
        _FakeLlama.made.append(kwargs)
        self.seen: list[list[str]] = []
        self.busy = False

    def tokenize(self, text: bytes, add_bos: bool = True) -> list[bytes]:
        assert add_bos
        return [b"<s>", *text.split(), b"</s>"]

    def detokenize(self, tokens: list[bytes]) -> bytes:
        return b" ".join(tokens)

    def embed(self, texts: list[str], normalize: bool = False) -> list[list[float]]:
        assert normalize
        assert not self.busy, "two threads inside one llama context"
        self.busy = True
        self.seen.append(list(texts))
        out = [[float(len(t)), 1.0, 0.0] for t in texts]
        self.busy = False
        return out


def _gguf(tmp_path: Path) -> Path:
    path = tmp_path / "model.gguf"
    path.write_bytes(b"GGUF")
    return path


def _embedder(tmp_path: Path, **kwargs: Any) -> LlamaCppEmbedder:
    return LlamaCppEmbedder(model_id="acme/m-q8_0", dim=3, path=_gguf(tmp_path), loader=_FakeLlama, **kwargs)


def test_surfaces_model_id_and_dim(tmp_path: Path) -> None:
    emb = _embedder(tmp_path)
    assert (emb.model_id, emb.dim) == ("acme/m-q8_0", 3)
    assert isinstance(emb, Embedder)


def test_loads_once_with_the_pooling_and_one_sequence_per_decode(tmp_path: Path) -> None:
    _FakeLlama.made.clear()
    emb = _embedder(tmp_path, pooling="cls", max_tokens=512)
    emb.embed_documents(["a"])
    emb.embed_query("b")
    assert len(_FakeLlama.made) == 1
    made = _FakeLlama.made[0]
    assert made["embedding"] is True
    assert made["pooling_type"] == 2
    assert made["n_ctx"] == made["n_batch"] == made["n_ubatch"] == 512
    assert made["n_gpu_layers"] == -1


def test_documents_and_queries_share_one_encoding_with_their_own_prefix(tmp_path: Path) -> None:
    emb = _embedder(tmp_path, query_prefix="q: ", document_prefix="d: ")
    emb.embed_documents(["one two"])
    emb.embed_query("one two")
    llm = emb._llm
    assert llm.seen == [["d: one two"], ["q: one two"]]


def test_a_long_text_keeps_its_first_tokens(tmp_path: Path) -> None:
    emb = _embedder(tmp_path, max_tokens=5)
    emb.embed_documents(["w1 w2 w3", "w1 w2 w3 w4 w5 w6"])
    # 5 tokens = <s> + 3 content + </s>
    assert emb._llm.seen == [["w1 w2 w3", "w1 w2 w3"]]


def test_no_texts_loads_nothing(tmp_path: Path) -> None:
    _FakeLlama.made.clear()
    assert _embedder(tmp_path).embed_documents([]) == []
    assert _FakeLlama.made == []


def test_threads_never_share_the_context(tmp_path: Path) -> None:
    emb = _embedder(tmp_path)
    errors: list[BaseException] = []

    def run() -> None:
        try:
            for _ in range(50):
                emb.embed_query("x y")
        except BaseException as exc:  # noqa: BLE001 — reported below
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


def test_a_wrong_dimension_fails_loud(tmp_path: Path) -> None:
    emb = LlamaCppEmbedder(model_id="acme/m", dim=8, path=_gguf(tmp_path), loader=_FakeLlama)
    with pytest.raises(AnyEmbedError, match="3 dims"):
        emb.embed_query("x")


def test_a_missing_file_fails_loud(tmp_path: Path) -> None:
    emb = LlamaCppEmbedder(model_id="acme/m", dim=3, path=tmp_path / "absent.gguf", loader=_FakeLlama)
    with pytest.raises(AnyEmbedError, match="not found"):
        emb.embed_query("x")


def test_a_missing_repo_file_fails_loud_offline() -> None:
    emb = LlamaCppEmbedder(model_id="x", dim=3, repo_id="definitely-not/a-real-repo-xyz", filename="m.gguf", loader=_FakeLlama)
    with pytest.raises(AnyEmbedError, match="could not be found"):
        emb.embed_query("x")


def test_a_loader_failure_fails_loud(tmp_path: Path) -> None:
    def broken(**_kwargs: Any) -> Any:
        msg = "bad magic"
        raise RuntimeError(msg)

    emb = LlamaCppEmbedder(model_id="acme/m", dim=3, path=_gguf(tmp_path), loader=broken)
    with pytest.raises(AnyEmbedError, match="bad magic"):
        emb.embed_query("x")


def test_needs_a_path_or_a_repo_file() -> None:
    with pytest.raises(ValueError, match="needs"):
        LlamaCppEmbedder(model_id="x", dim=3)
    with pytest.raises(ValueError, match="pooling"):
        LlamaCppEmbedder(model_id="x", dim=3, path="m.gguf", pooling="max")  # type: ignore[arg-type]


# --- the real model, when its GGUF is in the local Hugging Face cache ------------------


def _real() -> LlamaCppEmbedder:
    emb = LlamaCppEmbedder(
        model_id="ggml-org/bge-m3-q8_0", dim=1024, pooling="cls", repo_id="ggml-org/bge-m3-Q8_0-GGUF", filename="bge-m3-q8_0.gguf"
    )
    try:
        emb.resolve()
    except AnyEmbedError:
        pytest.skip("bge-m3 GGUF not in the local Hugging Face cache")
    return emb


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_real_bge_m3_unit_vectors_and_query_document_parity() -> None:
    emb = _real()
    doc = emb.embed_documents(["The token bucket smooths bursty request rates.", "Сметана и творог."])
    query = emb.embed_query("The token bucket smooths bursty request rates.")
    assert all(math.isclose(sum(x * x for x in v), 1.0, rel_tol=1e-3) for v in [*doc, query])
    # One pooling on both sides: the same text is the same vector.
    assert _cos(doc[0], query) > 0.9999
    assert _cos(doc[0], doc[1]) < 0.9


def test_real_bge_m3_truncates_a_long_text() -> None:
    emb = _real()
    long = " ".join(["alpha beta gamma delta"] * 400)
    (vector,) = emb.embed_documents([long])
    assert len(vector) == 1024


def test_close_frees_the_model_and_the_next_call_loads_it_again(tmp_path: Path) -> None:
    _FakeLlama.made.clear()
    emb = _embedder(tmp_path)
    emb.embed_query("x")
    emb.close()
    assert emb._llm is None
    emb.embed_query("x")
    assert len(_FakeLlama.made) == 2


def test_a_process_that_loaded_the_real_model_exits_cleanly(tmp_path: Path) -> None:
    _real()
    script = (
        "from anyembed import LlamaCppEmbedder\n"
        "e = LlamaCppEmbedder(model_id='m', dim=1024, repo_id='ggml-org/bge-m3-Q8_0-GGUF', filename='bge-m3-q8_0.gguf')\n"
        "e.embed_documents(['one', 'two'])\n"
        "import gc; holder = [e]\n"  # alive at exit: freed by the atexit hook, not by module teardown
    )
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    assert "GGML_ASSERT" not in done.stderr
    assert "Exception ignored" not in done.stderr


def test_count_tokens_counts_what_a_document_embeds_and_loads_only_the_vocabulary(tmp_path: Path) -> None:
    _FakeLlama.made.clear()
    emb = _embedder(tmp_path, document_prefix="d: ", max_tokens=4)
    assert emb.max_tokens == 4
    # "d: one two" is three words plus the two special tokens.
    assert emb.count_tokens(["one two", ""]) == [5, 3]
    assert [m.get("vocab_only") for m in _FakeLlama.made] == [True]


def test_count_tokens_uses_the_loaded_model_when_there_is_one(tmp_path: Path) -> None:
    _FakeLlama.made.clear()
    emb = _embedder(tmp_path)
    emb.embed_documents(["a"])
    assert emb.count_tokens(["a b c"]) == [5]
    assert len(_FakeLlama.made) == 1


def test_a_process_that_only_counted_tokens_exits_cleanly(tmp_path: Path) -> None:
    _real()
    script = (
        "from anyembed import LlamaCppEmbedder\n"
        "e = LlamaCppEmbedder(model_id='m', dim=1024, repo_id='ggml-org/bge-m3-Q8_0-GGUF', filename='bge-m3-q8_0.gguf')\n"
        "assert e.count_tokens(['one two'])[0] > 2\n"
        "holder = [e]\n"  # alive at exit: the vocabulary is freed by the atexit hook too
    )
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    assert "Exception ignored" not in done.stderr


def test_a_vocabulary_load_is_closed_at_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registered: list[Any] = []
    monkeypatch.setattr("anyembed.llamacpp.atexit.register", lambda fn, ref: registered.append(ref))
    emb = _embedder(tmp_path)
    emb.count_tokens(["a"])
    assert [r() for r in registered] == [emb]
