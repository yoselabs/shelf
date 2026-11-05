# jsonl-log — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.3.1: `append`/`append_at` on a file replaced under all 4 attempts: silent success ⇒ raises new `LineLostError(JsonlLogError)`
- 0.3.1: `JsonlLog(path: str, rotate_lock=True)` AttributeError ⇒ accepted, `True` = `<path>.lock` for `Path` and `str`
- 0.3.1: evicted held log: reopened descriptor kept (leaked) ⇒ closed after each append
