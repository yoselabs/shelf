---
id: 0018
title: A new blueprint checkpoint warns until the repo's next audit
statement: Each audit records the checkpoints it judged in docs/blueprint/checkpoints.txt; between audits the gate enforces that set and a newer checkpoint only warns (🆕).
concerns: [gate]
status: accepted
decided_by: owner
updated: 2026-10-11
distilled_into: blueprint runner.ACCEPTED; report.write
---

# 0018 — New checkpoints warn until the next audit

## Decision

The audit (`check --write`) writes `docs/blueprint/checkpoints.txt` (`id@version` per row). The
per-commit gate (`make blueprint`) fails only on rows in that set; a row added or changed in the
shelf since shows as 🆕 and does not fail. The next audit takes it in. A repo never audited enforces
everything; one audited before the record existed treats its non-passing rows as new.

Why: the shelf moving must not turn every consumer's pre-push red in the middle of unrelated work
(a2kay, 2026-10-11: `uv lock --check` landed and blocked its push).

## Rejected

- A version per rule with consumer pinning: per-rule bookkeeping for the same effect.
- Enforce immediately: strict, but breaks agents mid-task in repos that did nothing wrong.

## History

- 2026-10-11: decided (shelf-pqu).
