# Evaluating nondeterministic behaviour — the gap next to BENCH (2026-08-03)

Raw thinking, unresolved. Source: a2web ran four measurement spikes over two
days to decide whether to add a schema layer to its LLM extraction, and whether
its nine site handlers earn their keep. The *method* turned out to be more
reusable than either answer, and it is **not** the method `WORKFLOW: BENCH`
describes.

Written because the consumer's agent re-derived the whole procedure from
scratch, which is the same signal that produced resolution 0011 (two benches,
identical shape, existing nowhere in the loop).

---

## The gap

`WORKFLOW: BENCH` (resolution 0011) is explicitly for **tools**:

> Frame as keep/replace on a specific capability … **Model-free grade** — human-judge
> each output on the named axes … not LLM-judged.

That fits docx engines and PDF engines: deterministic tools, stable outputs, a
human can read two conversions side by side and see which kept the tracked
changes.

It does not fit what a2web was doing, on four counts:

| | BENCH (tools) | this (behaviour variants) |
|---|---|---|
| subject | two libraries | two prompts / two configs of ONE system |
| output | deterministic | different every run |
| oracle | human reads both | no human can read 100 outputs |
| verdict | "engine X kept the footnotes" | a difference of means with a confidence interval |

The second row is the one that changes everything. **A deterministic tool can be
judged once. A nondeterministic one cannot be judged at all without replicates**,
and the moment you have replicates you are doing statistics, not inspection.

So: a sibling workflow, not an extension of BENCH. Candidate name: `ABLATE`, or
`EVAL`. (BENCH answers *which tool*; this answers *does this change help*.)

---

## Where it actually got invoked (the "two instances" test)

The shelf's own rule is **extracted, never invented** — two real instances before
a pattern is lifted. Both are in a2web, same week, and the second literally
imported the first's judge rather than re-writing it:

1. **`entity_schema_v1/v2/v3`** — does adding a schema.org entity block to the
   extraction prompt make the system relay *less* of the page?
2. **`handler_ablation_v1`** — are nine site-specific handlers worth their
   maintenance, or does the generic path match them?

Both are "does this component earn its place", answered against a
nondeterministic system, on live inputs. Neither could have used BENCH's
model-free grade.

A third instance exists in shape if not in name: a2web's own `make bench`
(`llm_eval/`) scores three systems on four axes. That one predates all of this
and was written ad hoc.

---

## The lessons — what actually cost something to learn

Ordered by how expensive the mistake was, not by importance.

### 1. Prove the knob bites — in BOTH directions

The handler ablation's non-vacuity guard asserted "with handlers off, no round
reports `tier_used == site_handler`". It read a field that **does not exist on
the model**, so it returned `None` on both arms and could never fire. A guard
that reads as coverage while providing none — the exact failure the shelf's own
non-vacuity floors exist to prevent.

Caught only because the handler-*ON* arm also reported `None`, where a handler
had demonstrably run.

Then mutation-testing the fix found a **second** bug (the field is
`site_handler:<name>`, not a bare `site_handler`, so the corrected check would
have rejected every valid case), and a **third** (the field answers "which tier
supplied the body", not "did the handler run" — a handler can run and then be
overtaken by escalation).

> **Rule: mutate the ablation to the wrong seam and require the guard to fire;
> then run it correctly and require it to pass.** One direction is not enough —
> a one-sided check cannot distinguish "the ablation worked" from "the probe
> reads nothing".

Corollary specific to Python: patch the seam **the caller actually uses**. The
consumer did `from ..handlers import match_handler`, freezing the reference, so
patching the origin module would silently no-op.

### 2. Change ONE thing per arm, or you cannot attribute your own result

v1's experimental arm moved the schema block *and* added an instruction. It lost
on answer length — and the spike could not say which change caused it.

v2 added an arm holding the instruction out. Result:

```
  position alone   +3.0 chars   (null)
  instruction alone  −52.8 chars (significant)
```

**100% of the effect was the instruction, 0% was the position.** v1 had exactly
the same data and could not have said that.

> **Rule: for every compound change, add the arm that isolates each half.** The
> cost is one more arm; the alternative is a result you cannot act on.

### 3. The metric has to match the worry, or the null is meaningless

v1 scored recall against one broad fact inventory. A *correct narrow answer* to a
narrow question therefore scored ~0.13 — the inventory contained facts the
question never asked for. Two of seven pages sat at floor or ceiling and carried
zero discriminating power.

v2 split the oracle:

```
  core      facts that ANSWER the question   -> near ceiling by design;
                                                 a drop here is a regression
  adjacent  facts the page carries BESIDE    -> where "does it give less info"
            the question                        actually lives
```

The user's concern was completeness, so the instrument had to measure
completeness, not question-answering.

> **Rule: name the worry first, then build the metric that would move if the
> worry were true.** And check for floor/ceiling rows — they cost sample size
> while contributing no information.

### 4. Pair everything; the subject's variance is not the effect's variance

Page difficulty dominated the spread. An unpaired comparison of grand means would
have needed far more samples, and its null would have been indistinguishable from
"we didn't sample enough".

Paired within (page × replicate), the same data resolved ~4–6 points of recall
with 24 rounds.

> **Rule: the delta is computed within a matched round, never between means.**
> Report the confidence interval, and state what effect size the sample could
> have excluded — "null" alone is not a result.

### 5. Do not let your production error-recovery heal the signal

a2web parses LLM JSON through a tolerant funnel that applies per-field recovery
policy. Using it in the spike would have **repaired exactly the degradation the
spike was trying to observe**. The spike used a deliberately dumb parse instead.

> **Rule: a measurement that runs the subject's own error-correction measures
> the error-correction.** Strip it, and say so in the harness.

### 6. Report the null, and withdraw predictions that do not replicate

v1 flagged an index-thinning effect as its most decision-relevant finding, noting
its interval crossed zero. v2, with more arms and rounds, found **the sign
flipped**. It was noise.

The finding doc says so in a section headed "v1's signal did NOT replicate",
rather than quietly keeping the story it produced. Likewise the headline
prediction — that schema-shaping would cost content — was **not confirmed**, and
the design that shipped is justified by different evidence than the one that
motivated the work.

> **Rule: a spike that cannot publish "I was wrong" is a spike that will only
> ever confirm.**

### 7. Check which way your design biases, then see if the result survived it

The judge's fact inventory was built from whichever arm retrieved the larger
body — which penalises the smaller-body arm on facts it never received.

Rather than hand-wave it: on the five sites where the bias favoured the handler,
the handler still **lost three of five**. An effect that survives a bias pointing
against it is stronger evidence than one that needed a favourable one.

> **Rule: enumerate the biases your harness introduces and report the result
> conditioned on each.** Sometimes the bias makes the finding stronger.

### 8. Express cost as a fraction of the whole, not of the part you changed

The entity block cost **+85% completion tokens**, which sounds prohibitive, and
was reported that way for a day.

But the page text dwarfs the answer:

```
  +85%  of the OUTPUT
  +2.9% of the WHOLE call (mean page ~4.4k input tokens)
```

The decision flipped on that reframing.

> **Rule: a percentage is meaningless without its denominator. Report the delta
> against total cost per unit of work.**

### 9. Benefit needs an exchange rate, not a direction

"Does it help?" is unanswerable as a yes/no when the help and the cost are in
different units. The useful form:

```
  extra coverage delivered  /  extra tokens spent
```

That number is comparable across candidate features and is what a ship/no-ship
call actually consumes. Two of the three spikes could not compute it because they
only measured harm.

> **Rule: measure what the change DELIVERS, not only whether it damages
> anything.** "Not worse" is not a reason to ship.

---

## Sketch of the workflow, if it is worth naming

```
TRIGGER: a keep/add/remove decision about a component of a NONDETERMINISTIC
         system (a prompt clause, a heuristic, a whole subsystem) where a single
         run cannot settle it.

1. Name the worry. Build the metric that moves iff the worry is true.
   Split the oracle when the worry and the task differ (core vs adjacent).
2. Arms: control + one arm per ISOLATED change. Compound arms are for
   confirming, never for attributing.
3. Oracle fixed BEFORE any arm is scored, blind to arm identity, arms shuffled
   and relabelled per scoring call.
4. Replicate. Pair within (subject x replicate). Report CI and the effect size
   the sample could exclude.
5. Strip the subject's own error-recovery from the harness.
6. Prove the knob bites — mutate to the wrong seam, require failure; run
   correctly, require pass.
7. Report cost against the TOTAL, and benefit as delivered-per-unit-cost.
8. Publish the null and any prediction that failed to replicate.
```

Open questions before this becomes a resolution:

- **Is it shelf substrate or consumer doctrine?** The *lessons* are universal;
  the *harness* is not obviously a package. There may be a small piece in here
  (paired-delta + CI + non-vacuity assertions over arms) but a2web's version is
  entangled with its own fetch path. Generic-first would say: define what the
  class needs, then rank by a2web's diet — not extract a2web's diet.
- **Does it fold into BENCH or sit beside it?** Beside, on the evidence above —
  but the two share steps 1, 5 and 8, and a reader will ask why there are two.
- **`llm-eval` as a package?** The shelf already has `anyllm`, `llm-cache`,
  `llm-wobble`. A judge-harness would be a fourth in that family, and the user
  named it as wanting to be "part of our better LLM evaluation stack in the
  shelf". That is a real pull, but nothing here has been used by a second
  consumer yet — promotion-to-be-challenged (resolution 0013) says that is a
  reason to promote *sooner*, not to hold, so it is worth an explicit call
  rather than a default no.

## Not decided here

Nothing. This is a thought, per the docs pipeline (thoughts → tracks → missions →
resolutions). Turning it into `WORKFLOW: ABLATE` requires a resolution plus the
distillation into `agent-loop.md` in the same commit, and the loop is a
Constitution-touching surface — human confirms.
