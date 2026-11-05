---
id: 0028
title: The shelf and everything built on it are hard opinionated
statement: No optionality, no backward compatibility in code, no redundancy; behaviour is decomposed behind owners, injected as instances, and checked against the shelf first. Constitution Article IX.
concerns: [doctrine, design]
status: accepted
decided_by: owner
updated: 2026-11-05
distilled_into: docs/constitution.md Article IX
---

# 0028 — Hard opinions

## Decision

Add Article IX to the constitution (no optionality, no backward compatibility in code, no redundancy,
decomposition and isolation, dependency injection, shelf awareness). Owner, 2026-11-05: "Our systems should be
opinionated, hard opinionated. No optionalities, no backward compatibility, no redundancy. Those are hard
requirements for everything we build."

Narrowed by it, each amended in the text: Article VI ("duplicate locally"), Article VII (duplicate/skip becomes
keep-local for niche pieces only), Article VIII ("duplicate back" becomes demote back), doctrine idea 3.
Read with it: [ADR 0007](0007-evolve-on-monotonic-contracts.md) means no capability is lost at a merge, not that
an old API shape stays; [ADR 0018](0018-new-checkpoints-warn-until-the-next-audit.md) governs how a new check
rolls out to consumer repos, not code paths; the `deprecated` catalog state is a label. Kept: versions as git
tags with pinned consumers (a breaking change bumps the tag; no shims) and ADR 0022 (an exception is a named
row, not a flag).

## How each rule is checked

| Rule | Check | State |
|---|---|---|
| No optionality | review check; lint on boolean mode parameters | lint untested, to file |
| No backward compatibility | grep ban on shim / legacy / compat / deprecated in code | to file |
| No redundancy | reconciliation pass (VIII); duplicate-code check in the gate | tool untested, to file |
| Dependency injection | architecture fitness test: no module-level I/O or global state (python.md already states it) | to file |
| Decomposition and isolation | Article IV review trigger | exists |

Adopting the rule includes filing each missing check.

## Breaches already known

The gate's own mode switches (`SHELF_HOST_CHECK`, `GATE_LOCK`, `just check` vs `check-all`) are optionality in
dev tooling. Remove them or justify each under ADR 0022; not done here.

## Open

- Article IV says size is a smoke alarm, never a cap. The owner also wants a hard per-file size limit in
  task-loop. Not changed here; decide whether Article IV yields.

## Rejected

- Keep optionality as a convenience: a switch doubles the paths to test and keep honest.
- Backward-compat shims for consumers: pins already protect them, and a shim outlives its reason.

## History

- 2026-11-05: decided by the owner (quote above).
