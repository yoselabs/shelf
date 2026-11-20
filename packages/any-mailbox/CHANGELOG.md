# any-mailbox — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new. `Mailbox(path, lock=None, *, timeout=30.0)`; `post(update: (bytes|None) -> bytes|None) -> bool`; `take() -> bytes|None`; `peek() -> bytes|None`
- 0.1.1: takes its lock with `ProcessLock.acquire_exclusive` (process-lock 0.4.0); requires `process-lock>=0.4,<1`; no behaviour change
