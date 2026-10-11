---
id: 0011
title: Benchmarking is a named workflow (BENCH)
statement: Contested keep-vs-replace and build-vs-adopt calls between tools are decided by the BENCH workflow on isolated, model-free, dated evidence, not by reputation or inheritance.
concerns: [workflow]
status: accepted
decided_by: owner
updated: 2026-07-10
expires: 2027-01-10
distilled_into: agent-loop.md `WORKFLOW: BENCH` (new, peer workflow); referenced from `WORKFLOW: SEAM` (ADOPT's "WINS") and `WORKFLOW: RECONCILE`
---

# 0011 — Evidence-backed tool comparison is a first-class shelf workflow (BENCH)

## Decision

`WORKFLOW: BENCH` is a **peer workflow** (not a buried sub-procedure) for deciding keep-vs-replace
or build-vs-adopt between substrate tools on evidence. It is *invoked from* `SEAM` (ADOPT's "WINS"
when the win is contested) and `RECONCILE` (re-checking an inherited or aging choice), but stands
alone because it is substantial and reused across packages. Steps:

1. **Frame** as keep/replace on a *specific capability*, naming the axis that decides it.
2. **Corpus by isolation**, one capability per fixture. Isolate by *synthesis* for semantic formats
   (docx/pptx/xlsx: authoring a single-feature file loses no realism) and by *selection* of real
   documents for lossy formats (PDF/scans: a synthetic file is easier than reality and hides the
   divergence the bench exists to expose). Never the user's own data.
3. **Transient isolated installs** (`uv run --with <tool>`), never a declared dependency just to bench.
4. **Model-free grade**: human-judged on named axes, evidence quoted; score the incumbent too ("no
   difference" is decisive).
5. **Dated findings doc** under `bench/results/`, committed, re-runnable on future tool versions.
6. **Decide, then a ledger row**, then close the loop (ADR 0009). The bench answers "which tool"; a
   separate call answers "is it worth it."

Propagated: new `WORKFLOW: BENCH` block after RECONCILE; SEAM ADOPT's "WINS" points to it when
contested; RECONCILE uses it to re-check inherited choices.

## Rejected

- **Re-deriving the method each time.** The shelf ran the same exercise twice (pdf-engine, then
  docx-engine verification) with an identical shape that existed nowhere in the loop. The owner named
  it ("benchmarking different tools would be a crucial part of shelf itself"); two instances is the
  honest moment to extract the pattern, as with ADR 0009.

## Risk, accepted

BENCH is heavy (corpus, isolated runs, findings doc). The guard is the trigger: it fires only when
reputation or inheritance can't defend a *contested* choice. Most ADOPTs resolve on DEEP·STABLE·WINS by
inspection. If it is invoked for uncontested picks, tighten the trigger, not the workflow.

## History

- 2026-07-10: decided. Trigger: the two benches above. Expires 2027-01-10 (re-justify once BENCH has
  been invoked a third time from the loop, not just the two that seeded it). Track: governance /
  the promotion model.
