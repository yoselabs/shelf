# beads-client — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.1.0: `Bd.show` requires exactly one matching record; empty, multiple or mismatched replies -> `BdError("malformed")`; only issue-absence diagnostics -> None.
- 0.1.0: present malformed title/description/acceptance/dependencies -> `BdError("malformed")`; omitted optional defaults and dependency kinds remain.
- 0.1.0: existing `Bd.show` -> structural `TaskReadClient`; `testing.FakeTaskReadClient` and `task_read_contract` supply the owning semantic read seam.
- 0.2.0: existing `Bd.ready` -> structural `ReadyReadClient`; `FakeTaskReadClient(ready=, ready_fault=)` and `ready_read_contract` supply the owning ready-set seam.
- 0.3.0: additive  ⇒  `Bd.comment_once(bead, key, text) -> Comment`: at most one comment per caller-chosen stable `key` (marker line `[comment-key: <key>]` appended); reads the bead's comments first and returns the existing one, and after a failed or lost post reads back and returns the landed comment instead of posting again, raising the original error only when nothing landed; same-key calls in one process are serialized; two processes racing one key can still both post (no atomic keyed insert in bd)
