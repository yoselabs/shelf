---
id: 0020
title: prek runs every git hook, bd's included
statement: prek is the one hook manager; bd's events run from .pre-commit-config.yaml via `bd hooks run`; bd never installs hooks itself and core.hooksPath stays unset.
concerns: [gate, backlog]
status: accepted
decided_by: owner
updated: 2026-10-11
distilled_into: blueprint gate.hooks-recipe, gate.hooks-installed; recipes/pre-commit-config.yaml; tools/onboard/hooks.py
---

# 0020 — prek runs every hook

## Decision

`bd init --skip-hooks`; bd's five events are the first entries in `.pre-commit-config.yaml`
(`bd hooks run <event>`), `bd dolt push` runs on pre-push, `just check` on pre-push; `prek install`.
Never `bd hooks install`.

Why: bd injecting its block into another manager's hook file made a failing check stop blocking
commits (lefthook, husky, hand-written hooks).

## Rejected

- lefthook, husky, hand-written hooks with bd's injection: the failure above.
- pre-commit (Python): prek runs the same config, faster, as one binary.

## History

- 2026-10-10: decided; research `openspec/changes/blueprint-skill/research/hooks-and-beads.md`.
