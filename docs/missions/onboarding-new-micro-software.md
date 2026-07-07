# Mission — onboarding new micro-software

- **Status:** captured (2026-07-08), not yet built. Revisit near the end of the bootstrap arc.
- **Track:** governance / catalog
- **Shape:** a **runbook** (the deterministic procedure) + a **skill** (`catalog`/`onboard` — the judgment).

## The questions this mission must answer

Raised by Denis. Four distinct entry paths, one shared lifecycle gate.

1. **Create a NEW micro-software from scratch** (a library / framework / CLI / new `Kind`).
   - What are the key steps? The procedure/checklist: name → capability → contract file (born
     `candidate`) → the boundary test → the manifest → tag. What has to be done, in order.
   - How to think about it *as* micro-software from the first line (stop-caring litmus, deep-module
     guardrail, T0–T2 tier placement, the COMPUTE-vs-STATE law for any-* libs).

2. **Onboard software we should BUILD, with micro-software in mind.**
   - How should the agent *think* about micro-software while building app code? (reach-for-the-shelf-
     first; is this substrate scar tissue or product?)
   - How to **scan for easy cases** — the "this is really a shelf piece" detector during normal work.

3. **Promote something already built into micro-software and replace it.**
   - When in-app code earns graduation (Article VII: a 2nd consumer pulls it; rule-of-three).
   - The replace procedure: extract behind the contract, repoint the origin app, keep the tests.

4. **Create new micro-software that wraps / becomes third-party open source.**
   - How to think about authoring an open-source library as the Implementation behind a Contract.
   - Ties directly to the evaluation-harness insight (glossary: `Implementation = ours | third-party |
     hybrid-adapter`): a contract's tests are the tender; a qualifying OSS dep can win and our code
     dissolves into a thin adapter. Onboarding a third-party dep IS running it against the contract.

## Design anchors (already decided — this mission composes them, doesn't re-derive)

- **Constitution** Articles V–VIII (earned protection · shelf-first adopt · promotion-not-publication ·
  mandatory decay) are the gates every onboarding path passes through.
- **The `micro-software` K skill** is the decision framework (litmus, deep-module guardrail,
  build-vs-adopt hard gate, tier model, rule-of-three shelf).
- **The evaluation-harness** (R3 / glossary `Implementation`) turns "should we adopt this OSS lib?"
  into "run it against the contract's tests — did it go green?"

## Deliverable sketch (when built)

- `docs/runbooks/onboard-<kind>.md` — the deterministic checklist per entry path (1–4 above).
- A `catalog`/`onboard` skill — the judgment layer: scan-for-easy-cases, promotion decision, the
  replace-with-adapter move. Authored via the skill-authoring pipeline; never hand-waved.

*(Do not build yet. This file exists so the idea is not lost and has a home in the track system.)*
