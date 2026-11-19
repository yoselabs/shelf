# anyembed — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

## 0.6.0

- `LocalEmbedder(offline=True)` set `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` in `os.environ`  ⇒  passes `local_files_only=True` to `from_pretrained`; the process environment is never touched
- `EmbeddingCache`: raw sqlite3 + hashlib  ⇒  `sqlite_sidecar.connect` / `transaction`, `content_digest.digest_text`; file layout and key bytes unchanged (golden test on an old-code database)
- new deps: `content-digest>=0.2`, `sqlite-sidecar>=0.3`

## 0.5.0

- install: `anyembed` brings torch + transformers  ⇒  `anyembed[transformers]` brings them; `anyembed` / `anyembed[llamacpp]` bring neither
- `LocalEmbedder.embed_*()` without torch/transformers: `ModuleNotFoundError` (or `AnyEmbedError` "could not be loaded")  ⇒  `AnyEmbedError` naming `anyembed[transformers]`

Migration: a host that uses `LocalEmbedder` pins `anyembed[transformers]` (plus `llamacpp` if it
uses both). A host that imports torch or transformers itself and got them only through anyembed
declares them itself.
