## Why

Onboarding a new project as a shelf consumer *with beads* currently means reading three documents
that do not reference each other, and getting an ordering right that none of them states.

```
 consuming-the-shelf.md          onboard-a-consumer.md         adopt-beads.md (~300 lines)
 ├─ 1 pyproject git+tag deps     Phase A (mechanical):         ├─ bd init
 ├─ 2 guard install ────────┐    ├─ 1 guard install ───────┐   ├─ bd config ×2 + readback
 ├─ 3 paste resolver block  │    ├─ 2 paste resolver block │   ├─ chain bd dolt push
 └─ 4 copy linter preset    │    ├─ 3 copy linter preset   │   ├─ Stop hook
                            │    └─ 4 deps come LATER      │   └─ AGENTS.md conventions
                            │                              │          ▲
                            └──────────────────────────────┴──────────┘
                              ORDERING: the guard must precede `bd init`, or bd seizes
                              core.hooksPath and the guard is installed dead.
                              Stated in none of the three.
```

Two of the three overlap almost entirely, beads appears in neither onboarding document, and the
one constraint that actually breaks a new project is unwritten.

`docs/missions/onboarding-new-micro-software.md:44` declares the consumer half **DONE**. This
session falsifies that. What exists is a description of the destination, not a path to it.

**The landmines a new project hits, in order of when it hits them:**

| # | landmine | tracked as |
|---|---|---|
| 1 | guard-before-`bd init` ordering is unwritten | this change |
| 2 | `install.py` writes to a directory git may not read | `shelf-efh` |
| 3 | the guard is the *sole* enforcement — the new project inherits a single point of failure | `shelf-gag` |
| 4 | resolver block and linter preset are manual copies that drift from source | this change |
| 5 | `.beads/config.yaml` is tracked, so git operations silently revert it | this change |
| 6 | nothing verifies the finished result | this change |

And the one that reshapes the plan: **`make bootstrap` cannot bootstrap greenfield.** The
`bootstrap-target-contract` change (`shelf-abf`) assumes a repo that already has the Makefile —
but the Makefile arrives at step 4 of onboarding. Something must run before the target repo has
anything, which is exactly the precedent `tools/hooks/install.py` already sets: a program that
lives in shelf and runs in the consumer's root.

## The governing decision: prose for judgment, execution for ordering

Onboarding must be **adaptive** — a target repo may be greenfield or established, may already run
husky or the pre-commit framework, may or may not want beads, may not be Python at all. That is
judgment, and judgment is what a skill is for.

But this session's whole lesson is that prose cannot enforce ordering or verification. A skill
that walks an agent through ordered steps is the failure mode, restated in a new file.

So the split is by **kind of knowledge**, and it is the load-bearing decision of this change:

- **The skill decides** *what this repo needs* — read the repo, choose the operations. Prose is
  correct here; there is nothing to enforce, only to weigh.
- **The operations enforce** *order and effect*. Each is idempotent, checks its own preconditions,
  and asserts its own result. Ordering is a **precondition the operation refuses to proceed
  without** — not a step the skill is trusted to remember.

The consequence worth stating plainly: invoking the operations in the wrong order fails loudly,
whether the caller is this skill, a different agent, a `make` target, or a person. Correctness
does not depend on the skill being read, being current, or being followed.

## What Changes

1. **An operation set, stack-tagged.** Small, idempotent, self-verifying units with declared
   preconditions:

   | operation | kind | notes |
   |---|---|---|
   | `guard` | stack-agnostic | exists as `tools/hooks/install.py`; needs `shelf-efh` first |
   | `resolver-block` | stack-agnostic | marker-delimited and re-projectable, replacing the manual paste (landmine 4) |
   | `beads` | stack-agnostic | `bd init` + config + the `bd dolt push` chain; **precondition: `guard` completed and verified** (landmine 1) |
   | `verify` | stack-agnostic | asserts every applied operation is live (landmine 6) |
   | `linter-preset` | python+uv | the ruff/codespell/coverage blocks, Makefile targets, dev group |

   Per your answer, only the Python+uv preset is implemented; the stack tag is where a second
   stack would attach. No abstraction is built for a stack that does not exist — that is the
   constitution's "do NOT build on spec".

2. **An `onboard-consumer` skill** carrying the judgment: detect the repo's current state, decide
   which operations apply, invoke them, and report what it could not do. Reached the way agents
   already reach shelf behaviour — via the resolver block's `$SHELF_HOME` lookup.

3. **The three onboarding documents collapse to one path.** `consuming-the-shelf.md` stays the
   canonical *description* of what a consumer is. `onboard-a-consumer.md` keeps the catch-up
   sweep — genuinely different work — and stops duplicating Phase A. Both point at the skill for
   the mechanical path.

4. **`beads` becomes part of onboarding**, opt-out rather than a separate runbook the onboarding
   documents never mention.

5. **The mission's "consumer half: DONE" claim is corrected**, with what was actually missing.

## Non-goals

- **A template repo.** It drifts from shelf the moment shelf changes, and cannot onboard a
  project that already exists — which is most of them.
- **Auto-adding shelf dependencies.** `onboard-a-consumer.md` Phase A step 4 is deliberate: you
  add a shelf dep when the sweep says *adopt*, never as a side effect of onboarding. Preserved.
- **Replacing `make bootstrap`.** See below — it becomes a thin entry point over these
  operations rather than a competing implementation.
- **Building the `catalog`/`onboard` skill (`shelf-c2s`).** That is the *supply* side — getting
  micro-software into the catalog, four entry paths. Different work, stays deferred.
- **Non-Python toolchain support.** Structured for it (operations are tagged); not built.

## Relationship to the other changes

```
shelf-efh   fix install.py hooksPath resolution     ← the `guard` operation must work first
    │
    ▼
THIS        operation set + onboard-consumer skill  ← defines what an operation guarantees
    │
    ▼
shelf-abf   make bootstrap                          ← re-scoped: a repo-local entry point that
                                                       calls the same operations, for an
                                                       established repo in its own idiom
```

`shelf-abf` inverts: it was going to define bootstrap and have onboarding follow. Greenfield
cannot use a Makefile that does not exist yet, so the operations must come first and
`make bootstrap` becomes one caller of them. Its contract work (idempotent / ordered / verifying /
honest) survives intact — it just describes the operations rather than a Make target.

`shelf-gag` remains independent and first: enforcement belonging in `make check` rather than in a
per-clone hook is exactly what a *newly onboarded* project should inherit.

## Impact

- New: an operations module, an `onboard-consumer` skill, one spec.
- `docs/consuming-the-shelf.md`, `docs/runbooks/onboard-a-consumer.md`,
  `docs/runbooks/adopt-beads.md` — de-duplicated, pointed at the skill.
- `docs/missions/onboarding-new-micro-software.md` — the DONE claim corrected.
- `shelf-abf` re-scoped; its proposal needs updating when this lands.
- Every existing consumer (a2kay, a2web) was onboarded by the manual path and may carry any of
  landmines 2–6. Re-running onboarding against them is how that gets checked; it is idempotent
  by construction, so it is safe to run on an already-onboarded repo. Worth doing deliberately
  rather than assuming they are fine.
