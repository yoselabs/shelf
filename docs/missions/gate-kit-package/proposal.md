# Gate kit: scripts become packages, consumers drop their copies

Owner: shelf gate. Source: `docs/thoughts/2026-11-19-gate-and-blueprint-overhaul-menu.md`. Carries the mechanism of `gate-test-loop` and
the contracts of `blueprint-multi-stack-contracts`.

## Why

- The same scripts exist in several places. `tools/changed.py` and `tools/gate_state.py` are byte-identical to `packages/blueprint/src/blueprint/recipes/`
  and are copied again into consumers (a2kay owns a `gate_state.py`). `recipes/` holds more copied scripts (`check_coverage.py`,
  `check_dockerfile_pins.py`, `check_godot.py`, `unity_integrity.py`).
- Consumers reach into a shelf clone at run time: the guard and `preset_drift.py` are found through `SHELF_HOME`, `../shelf` or
  `~/Workspaces/shelf`, and the gate's `blueprint` step does the same. A repo cannot be gated on a clone that lacks a sibling checkout.
- Task-loop keeps its own, partly better, gate machinery (receipts keyed on closure, run guard, quarantine, reach report) outside the shelf,
  and vendors 22 shelf packages into a skill folder. OGY has no gate. a2kay has the most converged one.
- The shelf will gain packages in other languages. ADR 0021 says: migrate to moon's generic task graph when the shelf gets its first
  non-Python package (bead shelf-qgz). That trigger is now expected, so the neutral core must exist before it and must decide moon versus own.

## What changes

1. **A shelf package for the gate mechanism** (library plus a thin CLI over it), neutral of language: parallel step runner with budgets
   and per-step timing; changed-files listing; receipts and ledger; run guard (worker cap, hang limits, markers, quarantine, too-wide
   alarm); test lock or slots; gate state; the secret-scan call; the `reach` report. Stdlib or shelf packages only.
2. **Stack adapters** implement the interface of `blueprint-multi-stack-contracts` D2. The Python adapter holds the `pyproject.toml` graph,
   the `uv export` fingerprint, and pytest invocation; it is the only place that knows pytest or uv. Adapters are separate packages
   from the core so the core carries no Python assumption.
3. **`blueprint` becomes the one CLI**: `blueprint check`, `blueprint test`, `blueprint render`, `blueprint audit`. It dispatches on the declared
   stacks. The package CLI stays callable on its own for a repo that does not use blueprint's audit.
4. **Every ad hoc script in `tools/` and `recipes/` is either moved into a package or documented as repo content.** Generic: `changed`,
   `affected`, `gate_state`, `preset_drift`, `forbid-local-shelf-source`, the recipe scripts. Repo-specific (stay, declared as extra gate steps
   so they still get timing, budgets and receipts): the shelf's `catalog.py`, `size_caps.py`, `arch_rules.py`, `blueprint_fitness.py`.
5. **Consumers depend on the package by git+tag pin** and delete their copies and their `SHELF_HOME` lookups. No shim, no compatibility
   path (ADR 0028).
6. **Moon decision recorded**: an ADR that amends 0021. Default proposal: do not adopt moon; the neutral core with adapters is the
   task graph, because 0021's rejection reasons (53 generated `moon.yml` plus a generator; two defaults that serve stale passes) still hold
   and the core needs a per-package `uv export` fingerprint that moon's Python support does not provide. Revisit only if the second adapter
   proves too costly to write. This is the owner's decision; the design lays out both.
7. **Extraction from task-loop**, in order of certainty: run guard; receipt key and ledger; conftest and data-directory coupling rules with
   unique-path matching; the AST import-graph reader only if package-level selection proves too wide. Not extracted: the basename "strings" rule.
8. **Consumer migration**: a2kay (replace copies, flat gate to selected tests, keep its `slow` marker and fake-models rule, resolve its
   coverage override), task-loop (adopt the package, drop its own selector and ledger once the package covers them, re-run its stale audit),
   OGY (first adoption: bootstrap gate, hooks, config).

## Names

Per ADR 0008 and 0015 the packages are named for the deliverable (`any-<domain>`). Candidates: the core `any-gate`, the Python adapter
`any-gate-python`. Final names are picked at implementation (the `pick-name` skill exists for it).

## Not in this change

What the loop selects (`gate-test-loop`); what blueprint checks (`blueprint-multi-stack-contracts`); porting any shelf package to another language.
