# The shelf doctrine

The *why* behind the constitution (the rules) and the glossary (the vocabulary). Self-contained on
purpose — the shelf carries its own doctrine; you should not need to read anything outside this repo.

## What the shelf is

Small, individually-**ownable**, **composable**, **contract-guaranteed** software pieces — reused
across separate apps instead of re-written. The differentiator is ownability + composability +
contract-guarantee, **not** "micro" / smallness. Lineage: microservices / micro-frontends, but the
axis is *ownability*, not distribution.

## Why it exists

Frameworks and substrate are quirky; agents burn tokens and cognitive load fighting them. The shelf
turns recurring substrate-glue into thin, deep pieces an app can **stop caring about** — bridges now,
better foundations later. Improving one piece improves every consumer at once.

## The load-bearing ideas

1. **The contract is the unit of selection, not the code.** Code is a regenerable phenotype; the
   contract (typed I/O + invariants + acceptance scenarios) is the gene; the record of kept contracts
   is its fitness. This is why *shape* can change (rename, arg→struct) while the *promise* holds.

2. **A micro-software is a build-vs-adopt evaluation harness.** A contract's tests are a standing
   tender: our own code OR a third-party dependency can win. The winning end-state is often our code
   *dissolving into a thin adapter* over a qualifying dep (what `anyllm` did for LLM providers). You
   adopt on GREEN, never on hope.

3. **Adopt conservatively — only if DEEP · STABLE · WINS.** *Pulling a shelf dep into a consumer* is the
   cautious act: reuse is encouraged, the wrong abstraction is not, and duplication beats a shallow or
   churning dependency. The three gates pick candidates; a contract's tests adjudicate them.

4. **Promote aggressively — capitalize generic substrate at writing time; reconcile later** (resolution
   0006). The opposite posture from adopt: the moment you write a generic helper, a pattern wrapper, or an
   abstraction over an awkward stdlib/library API, home it in the shelf *then* — a self-assessed "this
   feels reusable" is enough; no second consumer required. The goal is that every app is mostly *business
   logic + dependencies*. Two guards keep this from becoming a junk drawer: it is always **extracted, never
   invented** (real code a real app needed — never an empty package to look complete), and **reconciliation
   is mandatory** (merge / split / delete / demote, with hindsight). The flexibility-vs-reuse balance is
   found at reconcile time, not guessed upfront. *Aggressive promote + conservative adopt + mandatory
   decay is self-correcting.* When a candidate is a **richer superset of a package that already exists,
   evolve to the superset rather than growing a sibling** (resolution 0007, the *monotonicity test*): if the
   merged contract **exposes more and removes nothing** — rich return over bare value, fail-loud over
   errors-as-values — converge everyone onto it; keep a narrower contract only for a *stated* requirement.

5. **Structure controls size, not caps.** A large file is a smoke alarm for a missing boundary, not a
   lint failure. Good decomposition makes files small; arbitrary caps manufacture the wrong abstraction.

6. **Conflict-freedom by structure.** Files are truth; indexes are *derived*, never hand-edited. One
   concept per file. Parallel agents add disjoint files and never collide — no locks, by design.

7. **Evolution is the point.** Absorb, merge, rename, deprecate freely — the lineage is an arc in the
   graph, the contract survives, the tests protect the use case. Decay is mandatory; a smaller shelf is
   a healthier one.

## How the docs fit together

```
doctrine.md      the why (this file)
constitution.md  the operating rules that follow from it (the 8 articles)
glossary.md      the vocabulary — TYPES only, never instances
resolutions/     specific decisions, each with an expiry
missions/        scoped future objectives (e.g. onboarding runbook + skill)
consuming-*.md   how a project onboards as a consumer
thoughts/        the messy origin exploration (kept, not authoritative)
```

## Lineage

Distilled from an audit of a2kay (the decomposition method: stop-caring litmus, deep-module guardrail,
build-vs-adopt gate, tier model, rule-of-three shelf) and a broader software-factory strategy (the
contract-as-unit-of-selection and the ledger-as-fitness-record). a2kay is a *donor of ideas* and the
*first consumer* — never a dependency of the shelf.
