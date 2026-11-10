# beads-client — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.1.0: `Bd.show` requires exactly one matching record; empty, multiple or mismatched replies -> `BdError("malformed")`; only issue-absence diagnostics -> None.
- 0.1.0: present malformed title/description/acceptance/dependencies -> `BdError("malformed")`; omitted optional defaults and dependency kinds remain.
- 0.1.0: existing `Bd.show` -> structural `TaskReadClient`; `testing.FakeTaskReadClient` and `task_read_contract` supply the owning semantic read seam.
- 0.2.0: existing `Bd.ready` -> structural `ReadyReadClient`; `FakeTaskReadClient(ready=, ready_fault=)` and `ready_read_contract` supply the owning ready-set seam.
