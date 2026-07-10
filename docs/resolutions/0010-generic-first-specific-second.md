# 0010 — A shelf package's capability is defined generically first, weighted by the consumer second

- **Status:** decided (2026-07-10)
- **Expires:** 2027-01-10 (re-justify once it has steered a few real package-shaping calls)
- **Track:** governance / the promotion model
- **Distilled into:** agent-loop.md `WORKFLOW: SEAM` (step 1, the generic-first framing before the four directions)

## The fork

During docx-engine-verification (convert-md's docx engine choice), the first
framing over-anchored on the live consumer: *"what does a2kay actually feed —
does its docx have tracked changes?"* — and nearly scoped the whole bench to
that. The user corrected it against the shelf's own doctrine: convert-md is
**generic document→markdown substrate**; "generally we work with docx" defines
the capability, and the consumer only *weights* it. Anchoring on the consumer's
current diet is exactly how a package accretes hidden single-consumer
assumptions and stops being reusable — the failure the whole shelf exists to
avoid.

## The rule

When shaping a shelf package (PROMOTE, EVOLVE, or picking what a capability must
cover), an agent reasons in two passes, in this order:

1. **Generic first — define the capability set.** What does this capability need
   across the *class* of inputs at large, independent of who is calling today?
   ("Convert docx" needs to handle headings, tables, footnotes, math, images,
   tracked changes — the whole grid, because docx-in-general has them.)
2. **Specific second — weight, don't scope.** Use the live consumer only to
   *rank* which capabilities are common (→ the light default path) versus rare
   (→ acceptable behind an opt-in extra or graceful degradation). The consumer
   sets priorities; it never sets the boundary.

**Corollary:** never narrow a package's capability grid down to a single
consumer's current diet. If a capability exists in the class, it gets
considered — even if today's only consumer doesn't exercise it. A capability the
consumer doesn't use becomes an opt-in or a documented gap, not an amputation.

This is the same instinct as `SEAM` step 1 ("compare against the CATALOG, never
against another consumer") pointed *inward* at the package being shaped: judge
by the general shape of the problem, not by one caller's momentary needs.

## What changes (propagated)

`WORKFLOW: SEAM` step 1 gains the generic-first framing: before choosing a
direction, define the capability generically; treat the triggering consumer as
weighting, not as the capability's boundary.

## The risk, named

Over-generalizing is real — a package that chases every theoretical capability
of a format becomes a kitchen sink (the anti-pattern the deep-module guardrail
and RECONCILE exist to catch). This rule is not "support everything maximally";
it is "*consider* the whole class, then let the consumer weight what ships in
the default versus behind an opt-in." The weighting pass is what keeps generic-
first from becoming gold-plating. If the two passes ever collapse into "build
the union of all capabilities," that is the smell to catch at RECONCILE.
