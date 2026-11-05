# any-contract — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new. `check_contract(local_number, remote, *, key, capabilities, capabilities_key) -> Violation | None`; `Violation(text)`
- 0.1.0: `diff_schema(want, have, path="") -> {path: (only_want, only_have)}`; `undeclared(found, known) -> (new, resolved)`
