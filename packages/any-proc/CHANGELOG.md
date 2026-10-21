# any-proc — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.2.0: `Health("starting")` terminal, `sup.terminal == "starting"`  ⇒  `State.starting`; `start()` returns it, `supervise()` neither kills nor respawns it
