---
id: 0010
title: Generic first, consumer second
statement: Define a package's capability across the whole class of inputs first, then let the live consumer only rank what ships by default versus opt-in; never narrow the grid to one consumer's diet.
concerns: [workflow]
status: accepted
decided_by: owner
updated: 2026-07-10
expires: 2027-01-10
distilled_into: agent-loop.md `WORKFLOW: SEAM` (step 1, the generic-first framing before the four directions)
---

# 0010 — A shelf package's capability is defined generically first, weighted by the consumer second

## Decision

When shaping a package (PROMOTE, EVOLVE, or choosing what a capability must cover), reason in two
passes, in this order:

1. **Generic first: define the capability set.** What does the capability need across the *class* of
   inputs at large, independent of today's caller? ("Convert docx" covers headings, tables,
   footnotes, math, images, tracked changes, the whole grid, because docx-in-general has them.)
2. **Specific second: weight, don't scope.** Use the live consumer only to *rank* capabilities as
   common (the light default path) or rare (behind an opt-in extra or graceful degradation). The
   consumer sets priorities, never the boundary.

**Corollary:** never narrow the grid to one consumer's current diet. A capability the consumer
doesn't use becomes an opt-in or a documented gap, not an amputation. This is `SEAM` step 1 ("compare
against the CATALOG, never another consumer") pointed inward at the package being shaped.
`WORKFLOW: SEAM` step 1 gained this framing.

## Rejected

- **Scoping to the live consumer.** During docx-engine-verification the first framing anchored on
  a2kay ("does its docx have tracked changes?") and nearly scoped the whole bench to that. The owner
  corrected it: convert-md is generic document-to-markdown substrate, "generally we work with docx"
  defines the capability and the consumer only weights it. Anchoring on the consumer's diet is how a
  package accretes hidden single-consumer assumptions and stops being reusable.

## Risk, accepted

Over-generalizing makes a kitchen sink (the anti-pattern the deep-module guardrail and RECONCILE
catch). The rule is "*consider* the whole class, then let the consumer weight what ships by default
versus opt-in"; the weighting pass keeps it from gold-plating. If the passes collapse into "build the
union of all capabilities", catch it at RECONCILE.

## History

- 2026-07-10: decided. Trigger: the docx-engine-verification correction above. Expires 2027-01-10
  (re-justify once it has steered a few real package-shaping calls). Track: governance / the
  promotion model.
