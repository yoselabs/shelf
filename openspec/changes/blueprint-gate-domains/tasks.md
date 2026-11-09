# Validation evidence

Tracking and completion state belong to shelf-50w.1 in Beads.

| Scenario / check | Evidence |
| --- | --- |
| Existing gate, clone, LFS, facts, pin and runner behavior | Focused suite: 225 passed |
| Ordered IDs, versions, generic layer, concern filter and audit selection | test_gate_rows_keep_their_order_metadata_and_audit_selection |
| Moved rule bodies retain behavior | AST comparison against integration HEAD, allowing declared helper names and removing registration decorators |
| Required normal gate | `uv run just check`: passed on the integrated Linux worktree |
| Unchanged size caps | All changed modules pass: registration 37 SLOC, domains 60–178, facts 211, runner 125, tests 623/175; functions at most 29 |
| Explicit changed-source strict types | All gate modules, facts and runner: zero errors |
| Broader source type verification | Explicit full blueprint check reports six errors in untouched main, backlog, Python pin and stack modules; reported to coordinator |

Linux validation does not satisfy the release's native Mac requirement. The parent
shelf-50w remains open for broader workflow-model adoption and consumer snapshots.

The normal project typecheck automatically excludes editable workspace source paths
(including blueprint/src); its zero-error result alone is not source coverage. The
explicit changed-source check supplies this repair's evidence. No typechecker
configuration or unrelated source was changed.
