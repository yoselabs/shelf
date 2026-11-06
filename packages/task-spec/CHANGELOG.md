# task-spec — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new. `Task`, `Finding`, `Trust`, `Remedy`, `Ask`, `AskKind`; protocols `TaskStore(get, all, save)`, `AttentionStore(ask, pending, resolve)`; `task_spec.testing` stores and contracts
