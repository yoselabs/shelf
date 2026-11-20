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

**The aim it is pointed at: a standard library for the stuff a real app actually needs** — the layer
you reach for before writing anything, the way you reach for `pathlib` instead of splitting a path
by hand. That sets the bar at *how little a consumer must type*, not only at *what breaks without
us*: a domain whose library is correct but verbose is shelf material (ADR 0015). It does not
relax **extracted, never invented** — a standard library that fills with speculative packages is a
junk drawer with ambition. Breadth of subject and richness of surface are licensed; guessing that a
need exists is not.

## The philosophy of use: how every shelf package is shaped

> **⚠️ THIS IS THE SHELF'S FOUNDING PHILOSOPHY. NO MATTER WHAT, FOLLOW IT.**
> **⚠️ A package that breaks these six points is defective, however well it works.**
> **⚠️ Owner's words: "It's like a Bible of how shelf works." (Denis, 2026-11-20)**

Most people use a package through its defaults, and most of them in the same way. So the default must be the best
thing for that common use, and everything else must stay reachable by calling something, never by switching a mode.

1. **Simple things simple, complex things possible** (Alan Kay). The common call is one line with no setup. A rare
   need costs more code, but it is never impossible and never a rewrite.
2. **Data first: one complete, lossless value** (Rich Hickey). A package returns and stores ONE value that carries
   everything it knows, in ONE file. Not one file for the text and another for the speakers; not a summary now and
   the raw data later. Anything a consumer might need is in the value, because only a complete value lets every
   consumer be satisfied. What costs real work to produce (a second model, a network call) is opt-in; what is free
   to keep is kept.
3. **Views are functions, not modes** (progressive disclosure). What a reader sees comes from small pure
   functions on the value (a *projection*: `to_markdown()`, `.words`, `to_srt()`). The default view serves the
   most common reader; a narrower or wider view is another function the caller reaches for. A flag that changes
   *what is computed* is forbidden (Article III); a function that shows *part of what is there* is the pattern.
4. **The pit of success.** The easiest path is the correct path. Wrong use is hard to type and fails loud: the
   default is safe, a missing setup raises instead of falling back, a dangerous capability asks to be named.
5. **The default serves the common reader; the value serves every reader.** Today the common reader is an AI
   (tokens are money), so the default view is compact. The stored value stays complete. These two never trade off,
   because they live in different layers: value below, view above.

6. **Breaking is free.** The cost of changing a shape is a loud failure and a fast fix, never a reason to keep a wrong shape.
   Shelf is never held back by a caller it can break (Article III).

*Worked example:* any-speech stores one `<name>.speech.json` holding words, times, probabilities, speakers and
provenance. `to_markdown()` and `any-speech text` give the compact, token-cheap turn lines an AI should read.

## The load-bearing ideas

1. **The contract is the unit of selection, not the code.** Code is a regenerable phenotype; the
   contract (typed I/O + invariants + acceptance scenarios) is the gene; the record of kept contracts
   is its fitness. This is why *shape* can change (rename, arg→struct) while the *promise* holds.

2. **A micro-software is a build-vs-adopt evaluation harness.** A contract's tests are a standing
   tender: our own code OR a third-party dependency can win. The winning end-state is often our code
   *dissolving into a thin adapter* over a qualifying dep (what `anyllm` did for LLM providers). You
   adopt on GREEN, never on hope.

3. **Adopt conservatively — only if DEEP · STABLE · WINS.** *Pulling a shelf dep into a consumer* is the
   cautious act: reuse is encouraged, the wrong abstraction is not, and a single local implementation beats a shallow or
   churning dependency. The three gates pick candidates; a contract's tests adjudicate them.

4. **Promote aggressively — capitalize generic substrate at writing time; reconcile later** (ADR
   0006). The opposite posture from adopt: the moment you write a generic helper, a pattern wrapper, or an
   abstraction over an awkward stdlib/library API, home it in the shelf *then* — a self-assessed "this
   feels reusable" is enough; no second consumer required. **But "the moment you write" is not the only
   moment** (ADR 0012): a **sharp edge** — a dependency that is correct, documented, and correctly
   used, which still hurt a competent engineer — is discovered while *debugging*, and at that moment it
   looks like a bugfix rather than substrate. There the code is trivial and the discovery was expensive,
   so what the shelf capitalizes is the **lesson**, not the lines. The goal is that every app is mostly
   *business logic + dependencies*. Two guards keep this from becoming a junk drawer: it is always **extracted, never
   invented** (real code a real app needed — never an empty package to look complete), and **reconciliation
   is mandatory** (merge / split / delete / demote, with hindsight). The flexibility-vs-reuse balance is
   found at reconcile time, not guessed upfront. *Aggressive promote + conservative adopt + mandatory
   decay is self-correcting.* **A third trigger, quieter than both** (ADR 0015): a dependency
   that is correct and merely *verbose* — you wrote the expression and thought "why isn't this a
   method?". No bug, no glue, so neither other trigger fires; promote it anyway, and promote the
   **thing** (a type the consumer holds, owning its lazy reading and its derivations) rather than a
   drawer of functions over the library's own type. Name it `any-<domain>`, never `<lib>-extra`;
   one library underneath earns the prefix as well as five, and fusing two to get the better half of
   each is a `composite`. When a candidate is a **richer superset of a package that already exists,
   evolve to the superset rather than growing a sibling** (ADR 0007, the *monotonicity test*): if the
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
constitution.md  the operating rules that follow from it (the 9 articles)
CONTEXT.md      the vocabulary (root file) — TYPES only, never instances
adr/             living decisions (ADRs), one per topic; adr/INDEX.md is the list
missions/        scoped future objectives (e.g. onboarding runbook + skill)
consuming-*.md   how a project onboards as a consumer
thoughts/        the messy origin exploration (kept, not authoritative)
```

## Lineage

Distilled from an audit of a2kay (the decomposition method: stop-caring litmus, deep-module guardrail,
build-vs-adopt gate, tier model, rule-of-three shelf) and a broader software-factory strategy (the
contract-as-unit-of-selection and the ledger-as-fitness-record). a2kay is a *donor of ideas* and the
*first consumer* — never a dependency of the shelf.
