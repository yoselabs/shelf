---
id: 0028
title: The shelf and everything built on it are hard opinionated
statement: No optionality, no backward compatibility in code, no redundancy; behaviour is decomposed behind owners, injected as instances, and checked against the shelf first. Constitution Articles II and III.
concerns: [doctrine, design]
status: accepted
decided_by: owner
updated: 2026-11-05
distilled_into: docs/constitution.md Articles II, III
---

# 0028 — Hard opinions

## Decision

Fold the rules into the constitution without a new article: Article II (decomposition and isolation, dependency
injection) and Article III (no optionality, no backward compatibility in code, no redundancy);
shelf awareness joins Article VI. Owner, 2026-11-05: "Our systems should be
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
| No redundancy | `test_no_intra_package_body_duplication`, `test_no_cross_package_body_duplication` (ADR 0005); reconciliation pass (VIII) | exists, blocking |
| Dependency injection | architecture fitness test: no module-level I/O or global state (python.md already states it) | to file |
| Decomposition and isolation | Article IV per-file limit in the repo linter | exists in task-loop once its ratchet is replaced |

Adopting the rule includes filing each missing check.

The gate's mode switches `SHELF_HOST_CHECK` and `GATE_LOCK` (and the Docker gate behind them) are removed (2026-11-05). `just check` vs `check-all` (changed files vs all) stays: it is scope, not a behaviour switch.

## Open

- Article IV was amended on the owner's word (2026-11-05): size is a hard limit for code; only data files and code that cannot comply may exceed it. A size review trigger is no longer enough.

## Rejected

- Keep optionality as a convenience: a switch doubles the paths to test and keep honest.
- Backward-compat shims for consumers: pins already protect them, and a shim outlives its reason.

## History

- 2026-11-05: decided by the owner (quote above).
- 2026-11-05: the gate's mode switches (`SHELF_HOST_CHECK`, `GATE_LOCK`, the Docker gate) were removed; `just check` runs natively.
