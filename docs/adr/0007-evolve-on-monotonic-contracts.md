---
id: 0007
title: Evolve on monotonic contracts
statement: Evolve the one package to the richer superset instead of cutting a sibling; converge on a contract that exposes more and removes nothing, and keep a narrower one only for a stated requirement.
concerns: [workflow]
status: accepted
decided_by: owner
updated: 2026-07-08
expires: 2027-01-08
distilled_into: agent-loop.md WORKFLOW: SEAM (EVOLVE direction)
---

# 0007 — Evolve on a monotonic contract: one call, one response, expose more never less

## Decision

When a candidate is a richer superset of a package the shelf already has, **evolve the one package**
and do the reconciliation *in the moment*, rather than cutting a sibling and promising to merge later
(ADR 0006's "reconcile later" is for over-reach found with hindsight, not a licence to ship
known-duplicate siblings). Decide each contract axis by the **monotonicity test**: does the new shape
**expose more and remove nothing**?

- Only expands exposure (more returned, surfaced, expressible), reduces nothing a caller relied on:
  **converge everyone on it**. The thin caller ignores the extra.
- **Escape valve:** keep the narrower contract only where a consumer has a **stated, specific
  requirement**. Absent that, a second contract is just quirk.
- Where an axis is not strictly monotonic (a changed call convention), pick **the superset that can
  express the other**.

First case, `anyllm` (sync `complete(prompt)->str`, fail-loud) vs a2web's `Provider` (async,
accounting, cache breakpoints). Net: **one `complete`, one `Completion`, fail-loud, no sibling**.

| Axis | Unified contract | Why |
|---|---|---|
| Response | rich `Completion` (text, tokens, `cost_usd`, `latency_ms`, cache tiers) | adds accounting, removes nothing; thin caller reads `.text` |
| Failure | fail-loud `AnyLLMError(retryable, hint)` | raising surfaces failure; errors-as-values hides it as an empty string |
| Call | async + structured `complete(*, system, user, model, ...)` | can carry a flat sync prompt (`user=prompt, system=()`); the reverse cannot carry concurrency or a system/cache split |

a2web's degrade-to-raw is not a counterexample: its `Extractor` catches the loud `AnyLLMError` at
its own seam. The shared contract stays lossless; the consumer localizes its own leniency.

Mechanics for a breaking evolution of an *active* package (never delete a tag): `anyllm-v0.1.0`
stays; the superset ships as `anyllm-v0.2.0` with a migration note. a2web adopts v0.2.0 at once,
deletes its `providers/*` and `Provider` contract, keeps its `Extractor` composing on `anyllm`.
a2kay stays on v0.1.0; adopting is a reconcile item (ledger) done when it next touches its LLM
seam. The generic cache-tier token-to-cost accounting (`extract_token_counts` + pricing) and
`PromptParts` ride inside v0.2.0; extracting a tiny shared T0 is reconcile-later, only if a second
holder outside the LLM path wants them.

## Rejected

- **A sibling package.** It would split one Capability across two packages that disagree on what
  happens on failure, leaving two "stop caring which LLM" catalog entries. Monotonicity is what makes
  evolution safe: no caller loses anything it depended on.

## History

- 2026-07-08: decided; refines the EVOLVE-vs-sibling call in the four directions (agent-loop §2).
  Trigger: the first real case, a2web's LLM `Provider` vs `anyllm`. Expires 2027-01-08 (re-justify,
  especially whether any consumer ever needed the escape valve). Track: governance / promotion model,
  follows ADR 0006.
