# beads-client — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.1.0: `Bd.show` requires exactly one matching record; empty, multiple or mismatched replies -> `BdError("malformed")`; only issue-absence diagnostics -> None.
- 0.1.0: present malformed title/description/acceptance/dependencies -> `BdError("malformed")`; omitted optional defaults and dependency kinds remain.
- 0.1.0: existing `Bd.show` -> structural `TaskReadClient`; `testing.FakeTaskReadClient` and `task_read_contract` supply the owning semantic read seam.
- 0.2.0: existing `Bd.ready` -> structural `ReadyReadClient`; `FakeTaskReadClient(ready=, ready_fault=)` and `ready_read_contract` supply the owning ready-set seam.
- 0.3.0: additive  ⇒  `Bd.comment_once(bead, key, text) -> Comment`: at most one comment per caller-chosen stable `key` (marker line `[comment-key: <key>]` appended); reads the bead's comments first and returns the existing one, and after a failed or lost post reads back and returns the landed comment instead of posting again, raising the original error only when nothing landed; same-key calls in one process are serialized; two processes racing one key can still both post (no atomic keyed insert in bd)
- 0.4.0: breaking (0.3.0 only, `comment_once(bead, key, text)`)  ⇒  `Bd.comment_once(bead, text, *, key=None) -> Comment`: the comment is the one whose text equals `text` (whitespace trimmed); the body is posted as given, nothing appended; `key` (optional) appends `[comment-key: <key>]` for bodies that cannot be identical between attempts and matches on that line; read-before-post, read-back after a failed or lost post, same-text calls serialized in process
