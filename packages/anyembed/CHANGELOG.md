# anyembed — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

## 0.5.0

- install: `anyembed` brings torch + transformers  ⇒  `anyembed[transformers]` brings them; `anyembed` / `anyembed[llamacpp]` bring neither
- `LocalEmbedder.embed_*()` without torch/transformers: `ModuleNotFoundError` (or `AnyEmbedError` "could not be loaded")  ⇒  `AnyEmbedError` naming `anyembed[transformers]`

Migration: a host that uses `LocalEmbedder` pins `anyembed[transformers]` (plus `llamacpp` if it
uses both). A host that imports torch or transformers itself and got them only through anyembed
declares them itself.
