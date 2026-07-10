# 0011 — Evidence-backed tool comparison is a first-class shelf workflow (BENCH)

- **Status:** decided (2026-07-10)
- **Expires:** 2027-01-10 (re-justify once BENCH has been invoked a third time from the loop, not just from the two benches that seeded it)
- **Track:** governance / the promotion model
- **Distilled into:** agent-loop.md `WORKFLOW: BENCH` (new, peer workflow); referenced from `WORKFLOW: SEAM` (ADOPT's "WINS") and `WORKFLOW: RECONCILE`

## The fork

The shelf has now run the same exercise twice — pdf-engine-verification, then
docx-engine-verification — to turn an *inherited* engine choice into an
*evidence-backed* one. Both followed an identical shape that existed nowhere in
the loop: an agent re-derived the method from scratch each time. The user named
it directly: benchmarking different tools "would be a crucial part of shelf
itself… we'll need to do those exercises more and more with other software
later." Two instances is the honest moment to extract the pattern (the shelf's
own "extracted, never invented" rule; the same threshold at which resolution
0009 was written — after the practice existed, not before).

## The rule

`WORKFLOW: BENCH` is a **peer workflow** (not a buried sub-procedure): a named,
addressable procedure for making a keep-vs-replace / build-vs-adopt decision
between substrate tools on evidence rather than reputation. It is *invoked from*
`SEAM` (ADOPT's "WINS" claim, when the win is contested) and from `RECONCILE`
(re-checking an inherited or aging choice), but it stands on its own because it
is substantial and reused across unrelated packages.

Its load-bearing steps, generalized from both benches:

1. **Frame** as keep/replace on a *specific capability*, not "which tool is best"
   abstractly — name the axis that decides it.
2. **Corpus by isolation** — one capability per fixture. The transferable
   asymmetry: **isolate by *synthesis* for semantic formats** (docx/pptx/xlsx —
   authoring a single-feature file loses no realism) and **by *selection* of
   real documents for lossy formats** (PDF/scans — a synthetic file is easier
   than reality and hides the very divergence the bench exists to expose). Never
   the user's own data.
3. **Transient isolated installs** (`uv run --with <tool>`) — never a declared
   dependency just to bench it.
4. **Model-free grade** — human-judged on named axes, evidence quoted; score the
   incumbent too ("no difference" is decisive).
5. **Dated findings doc** under `bench/results/`, committed and re-runnable
   against future tool versions.
6. **Decide → ledger row**, then close the loop (resolution 0009). The bench
   answers "which tool"; a separate call answers "is it worth it."

## What changes (propagated)

- New `WORKFLOW: BENCH` block in agent-loop.md, placed with the promotion family
  (after RECONCILE).
- `SEAM` ADOPT's "WINS" criterion gains a pointer: if the win is contested,
  `BENCH` it rather than asserting it.
- `RECONCILE` gains BENCH as the tool for re-checking an inherited choice with
  evidence.

## The risk, named

BENCH is heavier than most loop steps — a corpus, isolated runs, a findings doc.
The guard against over-use is the trigger: it fires only when reputation or
inheritance genuinely isn't enough to defend a *contested* choice, not for every
adoption. Most ADOPTs still resolve on DEEP·STABLE·WINS by inspection; BENCH is
for when "WINS" is disputed on a capability that matters. If it starts getting
invoked for uncontested picks, that is the smell — the trigger, not the workflow,
is what needs tightening.
