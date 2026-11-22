---
id: 0033
title: Blueprint owns the standard gate steps; a repo that differs declares it, and nothing it runs goes unchecked
statement: Test units, node-tooling, recipe shadowing and calls, docker build --check, and worktree scope: gaps a2kay and homelab found are fixed in blueprint, never by weakening a checkpoint or silent override.
concerns: [gate]
status: proposed
decided_by: agent
updated: 2026-11-21
distilled_into: blueprint gate_units.py, unit_runner.py, gate.recipe-shadowing, gate.recipe-calls, node-tooling profile; beads shelf-scdi, shelf-xgi5, shelf-zmi5, shelf-nmdo, shelf-a6uy, shelf-cmbg, shelf-5j27
---

# 0033 — Blueprint owns the standard gate steps

Proposed by the agent; the owner has not decided. Choices for the owner to confirm: `docker build --check` counts; no `--gate` alias; the `node-tooling` detection rule; checkJs/JSDoc not a standard; the cache is per checkout; a unit's key fails closed beside reached code.

Owner rule (2026-11-21): the shelf decides which gates are standard; a repo does not need its own. If blueprint lacks something, fix blueprint; if the repo is wrong, fix the repo; never weaken a checkpoint to make a consumer pass; never override without a justification.

## Decision

- **Test units for a repo that is not a workspace** (`[tool.blueprint.test]` in `pyproject.toml`): units are paths; a unit's key hashes the files its tests reach (import graph, `conftest.py`, `reads` globs, `uv.lock`, the dependency and pytest/coverage parts of `pyproject.toml`). A change to shared code reruns every unit that reaches it; a unit-only change reruns only that unit.
- **Coverage survives skipping**: each unit's data is cached under its key (`gate-coverage` in the git directory every worktree shares) and combined with the fresh before the whole-repo floor. `coverage run -m pytest` and pytest-cov are both supported (pytest-cov breaks duckdb's lazy C-extension import). A unit with no cached data has no key, so it runs.
- **`gate.recipe-shadowing`**: a justfile that redefines a recipe blueprint renders (`.blueprint/*.just`) fails unless an `[[override]]` scoped to the recipe says why. `check-extra` is the declared extension point and is exempt. The shelf's own justfile shadowed six; shelf-5j27 moved their differences into data: `[tool.blueprint.gate]` (`lint-paths`, `spell-paths`, extra `steps`) and `[tool.blueprint.test] floor` in `pyproject.toml`, run by `blueprint gate lint|format|spell|test-all` (`gate_py`). `check-all` now runs `check-extra` too.
- **`gate.recipe-calls`**: a recipe that calls `blueprint` with a flag it does not have, or runs it from a shelf clone (`PYTHONPATH=…/shelf`, `--reference …shelf…`), fails. The pinned engine is `uv run blueprint`. The `--gate` flag stays removed (no alias): the row finds a recipe that still calls it.
- **`node-tooling` stack**: a `package.json` with scripts, none testing or type-checking, no TypeScript or test runner dependency, no `tsconfig.json`. Its `types` row is not applicable (no TypeScript; checkJs/JSDoc is the owner's choice, not a standard), `tests` is not applicable (another stack's runner judges them), `coverage` has no row. Formatter, linter, dependencies, architecture, hooks and toolchain stay and warn while unproven. Anything else with a `package.json` is `node`.
- **`stack.dockerfile.tests`**: a `docker build` (or `buildx build`) line in the gate must name the Dockerfile's path. `docker build --check` counts: BuildKit parses and lints, runs no layer, so a failing `RUN` is found only by a full build. A path in a comment or `echo` counts for nothing.
- **`gate.clean-clone`** prints the failing step (`gate: failed: …`) and the first 20 lines of its log; it no longer carries the unmerged-branches note (that note answers "is the gate missing", a different question).
- **`agents.worktrees-in-sync`** judges only the worktree the run is in, and the agent fixes it. The list of other sessions' worktrees is `agents.other-worktrees`, audit-only, the owner's.

- **Recipe meanings, the same in every repo** (owner, 2026-11-22: `check` is the full gate): `check` runs every step, narrowed to what the change reaches (changed files for per-file linters, affected tests only); `check-all` runs everything over everything and is opt-in (owner, 2026-11-22: it slows development; only a repo the owner marks critical has one, and no hook or agent runs it); `lint` is the static steps alone; `test` is the affected tests alone. A repo whose `check` is static-only renames it to `lint` and lets the rendered `check` stand (shelf-iost, closed: no setting names the gate recipe).

## Rejected

- A deprecated `--gate` alias: the removal was deliberate (`test_cli_topology`); the call check finds the stale recipe at the audit instead.
- Shipping the shadowing check with the shelf's six overrides: the goal is blueprint owning the steps, so the shelf deletes its copies once blueprint renders their forms.
- Requiring a full `docker build` and refusing `--check`: stricter, but breaks homelab's cheap proof for a gap the statement can name.

## History

- 2026-11-22: reviewed gate bugs fixed: invalid and unowned units refuse, filtered runs bypass coverage caches, test configuration and
  initializers invalidate keys, Just dumps resolve defaulted and imported shadows, calls respect quoting and continuations, Node installs
  follow the detected folder and lockfile, and lint preserves signal failures while running both tools.
- 2026-11-21: proposed, from the a2kay and homelab onboarding (a2kay-nhnh, a2kay-4r2p).
- 2026-11-22: recipe meanings added (owner: `check` is the full gate; affected tests only).
- 2026-11-22: `check-all` made opt-in; `[tool.blueprint.gate] release-gate = true` is built, and shelf opts in.
