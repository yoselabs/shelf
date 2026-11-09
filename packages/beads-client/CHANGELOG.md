# beads-client — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- Unreleased: `Bd.show` requires exactly one matching record; empty, multiple or mismatched replies -> `BdError("malformed")`; only issue-absence diagnostics -> None.
- Unreleased: present malformed title/description/acceptance/dependencies -> `BdError("malformed")`; omitted optional defaults and dependency kinds remain.
- Unreleased: existing `Bd.show` -> structural `TaskReadClient`; `testing.FakeTaskReadClient` and `task_read_contract` supply the owning semantic read seam.
