---
id: 0029
title: A repo's justfile imports blueprint-rendered parts; `import`, not `mod`
statement: The gate's common recipes are files `blueprint render` writes per stack; the repo's justfile imports them (`import`, not `mod`) and owns the rest; `render --check` is the drift check.
concerns: [gate, stack]
status: accepted
decided_by: owner
updated: 2026-11-20
distilled_into: blueprint render.py and just/*.just (the parts), `blueprint render` and `blueprint render --check`, the `render` gate recipe; mission blueprint-multi-stack-contracts task 8
---

# 0029 — the justfile imports blueprint-rendered parts

## Decision

- `blueprint render` writes `.blueprint/base.just` (the gate: `check`, `guard`, `preset`, `render`, `blueprint`, `steps`, `tools`, ...) and one
  `.blueprint/<stack>.just` per detected stack that has a part (python, shell). Plain text, deterministic: the same repo gives the same bytes,
  so a Rust blueprint can render the same files.
- The repo's `justfile` keeps `set allow-duplicate-recipes` and one `import '.blueprint/<part>.just'` per part, and owns everything else.
  `blueprint render` adds missing imports and never rewrites the rest.
- Extension points: a recipe defined in the repo's justfile replaces the base or stack recipe of the same name; `check-extra` (private,
  empty in the base) runs one more thing in the gate.
- `blueprint render --check` (the `render` recipe, a step of `check`) fails when a part differs from what would be rendered, is missing,
  belongs to a stack the repo no longer has, or is not imported. The recipe-set axis of `blueprint preset` is retired: it compared recipe
  names, which the rendered parts now fix.
- `blueprint test` is the one entry for the stack's tests: the adapter plans, `any-gate test` skips what passed and queues for the slot, the
  adapter's runner runs the rest. The python part's `test` recipe is `uv run blueprint test`.

## Why `import`, not `mod` (spike on just 1.58, 2026-11-20, two stacks)

- `mod` namespaces: `just base::check`, and `just check` is "does not contain recipe". A gate every consumer, hook and agent runs as `just check` would
  need an alias recipe per part, which is copying again. A module cannot depend on a parent recipe either, so the extension points are
  impossible.
- `import` flattens: `just check` stays, the parts' recipes depend on each other, and `just --dump --dump-format json` (what blueprint's
  gate checkpoints read) already sees the merged graph.
- Without `set allow-duplicate-recipes`, `import` refuses a recipe defined twice ("redefined"). With it the importing file's recipe wins,
  wherever the import sits, which is the override the repo needs. A recipe the repo overrides is not drift of the base.
- Variables are not overridable the same way, so the parts define none: the shelf's `lease_root` and `pytest_par` stay in its own justfile.

## Rejected

- `mod` per stack: see above.
- Copying recipe text (the old `linter_preset` copy list): ten repos reached ten gates, and drift could only be seen by name.
- Rendering into the repo's `justfile` between markers: the repo's own recipes and the rendered ones share one file, so a hand edit in the
  rendered region is a merge, not a diff.

## Consequences

- Only `bootstrap` and `bootstrap-verify` (they need a shelf clone) are still copied by onboarding.
- Consumers' `test` stops being whole-suite pytest with a coverage floor: it is the affected run without coverage; `just cov` measures.
  A repo that is not a `packages/*` workspace runs its whole suite as one unit.

## History

- 2026-11-20: decided by the owner's brief (justfile inherits from blueprint-owned base files with a drift check); `import` chosen over `mod` after a throwaway two-stack spike on just 1.58 (mission blueprint-multi-stack-contracts, task 8).
