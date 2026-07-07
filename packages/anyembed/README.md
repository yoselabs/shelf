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
