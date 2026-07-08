# 0007 — Evolve on a monotonic contract: one call, one response, expose more never less

- **Status:** decided (2026-07-08) — refines the EVOLVE-vs-sibling call in the four directions (agent-loop §2).
- **Expires:** 2027-01-08 (re-justify at the half-year — especially whether any consumer ever needed the escape valve).
- **Track:** governance / the promotion model. Follows [0006](0006-aggressive-capitalization-reconcile-later.md).

## The question this answers

Resolution 0006 said *promote aggressively*. It did **not** say what to do when a candidate is a **richer
superset of a package the shelf already has** — evolve the one package to the superset, or grow a *sibling*
beside it and reconcile later? The first real case: a2web's LLM `Provider` (async, token/cost/latency
accounting, prompt-cache breakpoints) vs `anyllm` (sync, `complete(prompt)->str`, fail-loud). Two shapes,
same Capability ("stop caring which LLM provider is underneath").

## The decision — the monotonicity test

**Prefer evolution over proliferation.** Do the reconciliation *in the moment* — grow the one package to
serve both — rather than cutting a second package and promising to merge later. A shelf of near-duplicate
siblings is the failure mode 0006's decay clause exists to prevent; don't manufacture the debt on purpose.

Decide each axis of the contract by whether the new shape is **monotonic** — does it **expose more and
remove nothing**?

- **If the new contract only *expands* exposure** (more returned, more surfaced, more expressible) and
  reduces nothing a caller relied on → **converge everyone onto it.** Evolve the package; the thin caller
  ignores the extra. This is a *good* contract change, not a breaking loss.
- **The escape valve:** keep the narrower contract **only** where a consumer has a **stated, specific
  requirement** for it. Absent that, a second contract is just quirk — resist it.

### Applied to anyllm (the first case)

| Axis | Old (`anyllm`) | New (a2web `Provider`) | Monotonic? | Unified contract |
|---|---|---|---|---|
| **Response** | bare `str` | `Completion` (text + tokens + `cost_usd` + `latency_ms` + cache tiers) | **Yes** — adds accounting, removes nothing; thin caller reads `.text` | **rich `Completion` everywhere** |
| **Failure** | raises `AnyLLMError(retryable, hint)` | errors-as-values (empty text + `raw["error"]`) | **fail-loud is the monotonic one** — raising *surfaces* the failure + retryable + hint; errors-as-values *hides* it as an empty string | **fail-loud everywhere** |
| **Call convention** | sync `complete(prompt)` | async `complete(*, system, user, model, …)` | not strictly monotonic (changes the call) — decided by **superset that can express the other**: async+structured can carry a flat sync prompt (`user=prompt, system=()`); the reverse can't carry concurrency or a system/cache split | **async + structured, one call** |

Two axes fall out of the monotonicity test; the third (call convention) is the one genuine pick, resolved
by "the superset that can express the narrower one." Net: **one `complete`, one `Completion`, fail-loud** —
`anyllm` evolves to the superset; there is no sibling.

**a2web's degrade-to-raw is *not* a counterexample to fail-loud.** It is a stated requirement satisfied at
a2web's *own* seam: its `Extractor` catches the loud `AnyLLMError` and produces its degraded
`ExtractionResult`. The shelf contract stays lossless; the consumer localizes its own leniency. That is the
escape valve working as designed — a requirement met by the consumer, not by weakening the shared contract.

## Mechanics (a breaking evolution of an *active* package)

`anyllm` is `active` and `a2kay` depends on it, so the response+call changes are **breaking**. Per the
opt-in-upgrade rule (never delete a tag):

- `anyllm-v0.1.0` **stays**. The evolved superset ships as **`anyllm-v0.2.0`** with a migration note.
- **a2web** adopts `anyllm-v0.2.0` immediately (it is the shape it already wrote), deletes its
  `packages/llm_extract/providers/*` + the `Provider` contract, and keeps its `Extractor` *composing* on
  `anyllm` — catching `AnyLLMError` at that seam for degrade-to-raw.
- **a2kay** stays on `anyllm-v0.1.0`; adopting `v0.2.0` is a **reconcile item** (ledger), done when a2kay
  next touches its LLM seam — no forced churn.

The generic Anthropic **cache-tier token→cost accounting** (`extract_token_counts` + pricing) and the
`PromptParts` cache-breakpoint helper are contract-neutral substrate *below* the provider interface. They
ride inside `anyllm-v0.2.0` for now; extracting them as a tiny shared T0 is a **reconcile-later** item,
taken only if a second holder outside the LLM path ever wants them (don't build it speculatively).

## Why not a sibling (the rejected option)

A sibling would have split one Capability across two packages that disagree on the one thing every caller
must reason about — what happens on failure — leaving the catalog with two "stop caring which LLM" entries.
Evolution keeps a single coherent contract and a single catalog line. The monotonicity test is precisely
what makes evolution *safe* here: because the unified contract only expands exposure, no caller loses
anything it depended on.

## Consequences

- The four directions (agent-loop §2) gain a sharper **EVOLVE-vs-sibling** rule: **evolve when the merged
  contract is monotonic (expands, reduces nothing); keep a narrower contract only for a stated requirement.**
- Reconcile **in the moment** is the default over promote-sibling-then-merge. 0006's "reconcile later" is
  for genuine over-reach discovered with hindsight, **not** a licence to ship known-duplicate siblings.
