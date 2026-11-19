---
id: 0021
title: The gate core is the shelf's own, one adapter per stack; moon is rejected
statement: Affected selection, receipts and the run guard live in a shelf-owned neutral core with one adapter per stack (Python first, via uv export). No external build tool.
concerns: [gate, tooling]
status: accepted
decided_by: owner
updated: 2026-11-19
distilled_into: docs/missions/gate-kit-package; tools/affected.py and the justfile check recipe until that change lands
---

# 0021 — The gate core is our own

## Decision

Narrowing the gate to what a change reaches, remembering green results, and guarding the run are done by a shelf-owned,
language-neutral core (`docs/missions/gate-kit-package`) with one adapter per stack. The Python adapter builds the unit graph from
`pyproject.toml` and fingerprints each package with `uv export` (measured 2026-11-19: median 1.5 suites per commit instead of 79). The
`blueprint` CLI is the one entry point and dispatches on the repo's declared stacks. Until that change lands, `tools/affected.py` and the
justfile's `test-affected` keep running the gate.

The owner expects blueprint itself may later be rewritten in Rust. So the core's contracts stay plain: a CLI, declarative config, and
receipt and render files in a documented text format, never a Python-only object or pickle.

## Rejected

- **moon** (trials 2026-10-10/11, reports in `docs/research/blueprint-skill/research/affected-*.md`): correct and fast warm (5-7 s), but
  53 generated `moon.yml` plus our generator, two defaults that silently serve stale passes, a Python toolchain that infers 3 of 6 edges and
  rewrites a stale `uv.lock`, no per-package `uv export` fingerprint. Adopting it would also make every repo covered by blueprint install it.
- **Turborepo**: green, but three experimental flags, uv support "can change at any time", wrote into AGENTS.md uninvited.
- **Nx**: graph and affected correct with a 101-line plugin; never run as the full gate.
- **Pants**: ignores `uv.lock`.
- **Task-loop's selector as is**: its basename "strings" rule adds about 30 test files per commit in a 79-package workspace; precision matches the
  package selector once it is off. The run guard, receipt idea and coupling rules are extracted instead.

## Revisit when

A second stack's adapter costs more than writing and keeping moon's generated config would. The trigger is adapter cost, not the number of
languages. The first non-Python package (the old trigger) now starts that second adapter instead of a migration.

## History

- 2026-10-11: decided to keep `tools/affected.py` and name moon the migration target for the first non-Python package, after round 3.
- 2026-11-05: the Turborepo trial's "drops the container gate" note is moot: the shelf has no container gate (ADR 0027).
- 2026-11-19: owner chose the own core over moon, after a replay of the last 50 commits showed the lock rule, not the selector, was the cost.
