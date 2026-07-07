# Mission — the contract layer + the `Implementation` build-vs-adopt harness

- **Status:** captured (2026-07-08), not yet built. The deepest idea in the design; **inert until a real
  contract need or a second consumer appears** — do not build on spec.
- **Track:** governance / the unit of selection
- **Shape:** a file format (`<pkg>/contracts/*.yml`) + a test-runner convention that turns "should we
  adopt this dependency?" into "did it pass the contract's tests?".
- **Source:** exploration doc R2/R3, the [glossary](../glossary.md) spine, constitution Articles V–VII.

## The idea in one line

A MicroSoftware is **a Contract + whichever Implementation currently wins its tests.** The contract is
the durable gene; the code (ours or a third-party dep) is a swappable phenotype. A contract's test suite
is a **standing tender** — any candidate that goes green can win, and the ideal end-state is our code
dissolving into a thin adapter over a qualifying dependency.

## The questions this mission must answer

1. **The contract file.** One contract = capability + invariants + binding (one line) + shape flag +
   acceptance→test + holdout→consumer-repo + owner + requester + status + expires. What is the exact
   schema? It IS a ledger row (R154) — how do the fields map so we don't build a second ledger?
2. **Shape: flexible vs pinned.** `flexible` (a facade absorbs rename / arg→struct — the default) vs
   `pinned` (the signature *is* the contract — only when serialized, passed to a 3rd lib, or hot-path;
   changing it = major bump + migration). How is the binding line authored and checked?
3. **Earned protection (Article V).** Every contract is born `candidate` (inert — cannot block a
   refactor) and becomes `active` only when a live consumer demonstrably breaks without it. What flips
   it, and what records the break?
4. **Anti-Goodhart for a solo shop** (one agent writes both the refactor and the test). The proposed
   defense: **holdout scenarios live in the consumer repo, run against the *published* artifact, in CI
   the refactor agent never sees** + mutation testing. Is that sufficient? How does it wire up?
5. **The `Implementation` entity — the harness proper.** `ours | third-party | hybrid-adapter`. The
   contract's tests are provider-agnostic; adopting an OSS dep = running it against the tests. What is
   the runner that adjudicates candidates and reports a winner? This makes constitution VI's
   build-vs-adopt gate **continuous and executable**, not a one-time human judgment.

## Design anchors (already decided — compose, don't re-derive)

- **Glossary** already names every entity: `Contract` (the gene, own file) · `Shape` (flexible|pinned) ·
  `AcceptanceScenario` (visible) · `HoldoutScenario` (hidden, consumer-side) · `Implementation`
  (swappable) · `UseCase`/`Sponsor`/`Owner`/`Requester` (the two hats).
- **Constitution V** (earned protection), **VI** (adopt only on GREEN, never on hope), **VII**
  (promotion-not-publication) are the gates.
- **The `micro-software` K skill** supplies the judgment (deep-module guardrail, build-vs-adopt gate).

## Deliverable sketch (when built)

- A `contracts/*.yml` schema + a tiny validator (one concept per file; born `candidate`).
- A test-runner convention that runs a contract's acceptance suite against any Implementation and
  reports pass/fail — the tender.
- The holdout mechanism: consumer-repo scenarios vs the published artifact, unseen by the refactor agent.

*(Do not build yet. Homed here so the crown insight is not stranded in a non-authoritative thoughts doc.
Trigger: the first real contract need, or a second consumer that makes a promotion's guarantee matter.)*
