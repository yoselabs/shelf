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

3. **Reach for the shelf first — but adopt only if DEEP · STABLE · WINS.** Reuse is encouraged; the
   wrong abstraction is not. Duplication beats a shallow or churning dependency. The three gates pick
   candidates; a contract's tests adjudicate them.

4. **Promotion, not publication.** A piece graduates into the catalog when a *second* consumer pulls
   it — never on a guess. (This is why the T0 primitives stayed in a2kay at bootstrap: n=1, unearned.)

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
