---
id: 0023
title: The gate runner is just
statement: Every repo's gate is a justfile run by a pinned `just` (`uv add --dev rust-just`, `uv run just check`); blueprint reads the gate graph from `just --dump --dump-format json`.
concerns: [gate]
status: accepted
decided_by: owner
updated: 2026-10-11
distilled_into: blueprint gate.runner, gate_graph.py; the shelf justfile; tools/onboard/linter_preset.py
---

# 0023 — The gate runner is just

## Decision

- **One runner for every repo:** a root `justfile`, recipes with the names the Makefile had
  (`check`, `check-all`, `lint`, `typecheck`, `arch`, `spell`, `deps`, `test`, `guard`, `preset`, `blueprint`, `bootstrap`, ...).
  Gate recipes carry `[group('gate')]`.
- **Pinned per repo:** Python repos `uv add --dev rust-just` and run `uv run just check` (1.58.0 was tested). Other stacks:
  `uvx rust-just@<version>`, brew, or a CI setup action. CI and the gate image run it the same way.
- **Blueprint reads the graph, not the syntax:** `just --dump --dump-format json` gives `recipes{name: dependencies,
  body, parameters, attributes}` and `assignments`. Walk from `check` through dependencies; an argument equal to a
  recipe name is an edge (`check: (gate "check-host")`); `{{var}}` in a body is resolved from the simple assignments.
  `just --dry-run check` replaces `make -n check`.
- **Rules for the file:** no backticks (`--dry-run` evaluates them, and blueprint dry-runs `check`); loops and
  multi-line shell in a shebang recipe, because just has no loops.
- **Migration:** `gate.runner` fails a Makefile-only gate and names the move. The other gate rows still read a Makefile
  (a fallback in `gate_graph.py`), so a repo not yet migrated is judged, not skipped. The row is a new checkpoint, so by
  ADR 0018 it only warns until the repo's next audit.

Why: the gate is read by agents, hooks, CI and blueprint. Make gave blueprint a regex over tab-indented text and a
dry-run that is unsafe by construction; just gives a JSON graph and a safe dry-run for one pinned dependency.

## Rejected

- **make:** no way to dump the graph (blueprint scrapes targets with regexes); `-n` still runs any recipe line naming
  `$(MAKE)` (the `container-%` dispatch had to move into its own target to be dry-run safe); `$$` escapes and
  mandatory tabs; no Windows story.
- **Taskfile:** the JSON listing has no dependencies; dispatch needs Go templates; dependencies run in parallel by
  default (order of the gate is part of its meaning); `--dry` still evaluates `sh:` variables.
- **mise tasks:** sequence edges (`depends` against run-lists) are invisible to a dump; no PyPI pin, so no
  `uv add --dev` pin per repo.
- **poe the poet:** Python only, and no graph dump.
- **nox, invoke, doit:** a Python program is the gate, so reading it means running it.
- **npm scripts:** a flat map of strings, no dependencies, and a Node requirement in non-Node repos.
- **A `scripts/` folder:** no graph at all, and every repo grows its own conventions.
- **dagger, earthly:** a container engine becomes a gate prerequisite, which the host fallback (`SHELF_HOST_CHECK=1`) exists to avoid.

## Weak spot

`just` is not preinstalled outside the uv pin: a machine with no `uv sync` yet has no `just`. Mitigations: `uv run just`
works on any clone with uv; `gate.one-command` reports "not checked" (never a pass) when `just` is missing.

## History

- 2026-10-11: decided by the owner after a runner comparison (make, just, Taskfile, mise, poe against the same
  gate); the shelf's Makefile became a justfile, and blueprint, onboarding, CI and the gate image moved with it.
