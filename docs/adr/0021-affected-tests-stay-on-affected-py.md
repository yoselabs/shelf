---
id: 0021
title: Affected-only tests stay on tools/affected.py; moon is the migration target
statement: make check narrows tests with tools/affected.py; no build tool yet. Migrate to moon's generic task graph when the shelf gets its first non-Python package (bead shelf-qgz).
concerns: [gate, tooling]
status: accepted
decided_by: owner
updated: 2026-10-11
distilled_into: tools/affected.py; Makefile check / test-affected
---

# 0021 — Keep tools/affected.py; moon next

## Decision

`tools/affected.py` (the uv-workspace dependency walk plus a pass cache) keeps narrowing `make check`
to the changed packages and their dependents. Every tool trialled works on the shelf today only with
config we would own anyway, and buys nothing until a second language lands.

**Notice: moon is the migration target.** Re-open shelf-qgz and migrate when the shelf gets its first
non-Python package, or when moon's uv support infers version-ranged dependencies (moonrepo/plugins#208).
Known setup from the trial: generic tasks only (not `unstable_python`), dependency edges generated from
pyproject, `cacheStrategy: hash` on task deps, plain `moon run :check` (not `--affected`).

## Rejected (trials 2026-10-10/11; reports in `openspec/changes/blueprint-skill/research/affected-*.md`)

- **moon** (round 2): correct and fast warm (5-7 s), but 53 generated moon.yml plus our generator,
  and two defaults that silently serve stale passes. Not now; target later.
- **moon with its Python toolchain** (round 3): infers 3 of 6 edges (ignores version-ranged
  dependencies, upstream bug), rewrites a stale uv.lock by default, still marked unstable.
- **Turborepo**: green, but three experimental flags, uv support "can change at any time", wrote into
  AGENTS.md uninvited, drops the container gate.
- **Nx**: graph and affected correct with a 101-line plugin; never run as the full gate.
- **Pants**: ignores uv.lock.

## History

- 2026-10-11: decided after round 3.
