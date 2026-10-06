# anyembed

Stop caring which embedding backend is underneath. A neutral `Embedder` interface
plus an in-process `LocalEmbedder` (the BGE `transformers` recipe). No dependency
on any host framework — failures raise `AnyEmbedError`, which you translate at the
seam.

```python
from anyembed import LocalEmbedder

emb = LocalEmbedder(
    model_name="BAAI/bge-small-en-v1.5",
    dim=384,
    query_prefix="Represent this sentence for searching relevant passages: ",
)
vectors = emb.embed_documents(["passage one", "passage two"])   # len == emb.dim each
q = emb.embed_query("a search query")
```

## The design law: hide compute, surface state

Compute (`embed_documents` / `embed_query`) is hidden and swappable. The **state**
— `(model_id, dim)` — is surfaced deliberately: persist it alongside your index, and
when either changes, rebuild rather than silently mixing incompatible vectors.

## `LocalEmbedder`

CLS-token pooling + L2-normalize (the BGE recipe), loaded once and lazily. By default
`offline=True`: the weights are expected to be a baked, on-disk asset, and a missing
model fails loud (`AnyEmbedError`) instead of downloading in the request path.

## `LlamaCppEmbedder` (the `[llamacpp]` extra)

The same embedding models as GGUF files on `llama.cpp` — on Metal, `bge-m3` Q8_0 scores
what the `transformers` model scores (cosine >= 0.999 per vector) at about a quarter of the
resident memory, with no torch in the embedding path.

```python
from anyembed import LlamaCppEmbedder

emb = LlamaCppEmbedder(
    model_id="ggml-org/bge-m3-q8_0",   # name the quantization: persist this beside your vectors
    dim=1024,
    repo_id="ggml-org/bge-m3-Q8_0-GGUF", filename="bge-m3-q8_0.gguf",  # or path=...
    pooling="cls",                       # the model's own recipe: cls | mean | last
)
```

- Documents and queries go through one encoding (same pooling, L2-normalized); only the
  optional `query_prefix` / `document_prefix` differ.
- Truncates by tokens at `max_tokens` (512), keeping the model's special tokens.
  `count_tokens(texts)` says how many tokens each document takes (prefix and special tokens
  included) from a vocabulary-only load, no weights and no GPU; a host that must not lose
  text routes the ones over `max_tokens` to an embedder with a longer limit.
- One sequence per decode (`n_ctx = n_batch = max_tokens`): on Metal, packing several
  sequences into one batch measured slower, not faster.
- Thread-safe: calls are serialized on one `llama.cpp` context.
- Offline by default: a repo-named file must already be in the Hugging Face cache.

## `EmbeddingCache`

Vectors by `(model_id, sha256(exact text))` in their own SQLite file, so rebuilding a
vector index (after damage, a schema or tokenizer change) is a lookup, not a re-embed.

```python
from anyembed import EmbeddingCache

cache = EmbeddingCache("embed-cache.sqlite", max_rows=500_000)   # LRU beyond the cap
started = time.time()
vectors = cache.embed(emb.model_id, texts, emb.embed_documents)  # computes only the misses
cache.prune(unused_since=started)  # after a full pass: drop what the corpus no longer has
```
