---
id: 0015
title: Ergonomics is a capability
statement: A verbose-but-correct dependency is a promotion trigger; any-* promises a whole domain, not a backend swap, and where a domain has a thing, promote the thing, not a bag of functions.
concerns: [workflow, packaging]
status: accepted
decided_by: owner
updated: 2026-09-18
expires: 2027-09-18
distilled_into: agent-loop.md `WORKFLOW: SEAM` (a third trigger, the ergonomics complaint; PROMOTE gains the surface-shape rule), `WORKFLOW: PROMOTE` step 3 (the shape sub-step), `WORKFLOW: RECONCILE` (the bag-of-functions question)
---

# 0015 — Ergonomics is a capability: the surface promotes, and `any-*` is not only about swapping backends

## Decision

> **An ergonomics gap is a promotion trigger.** If a dependency is correct and you still had to write
> an expression you wish were a method, that expression is substrate; promote it. "Stop caring about
> X" includes *how much you must type to use X*, not only which implementation is underneath.

This is SEAM's **third trigger** (after "about to write glue" and ADR 0012's bugfix): the dependency
is correct, documented, correctly used, did not bite, it was just **verbose** ("why isn't this a
method?"). Nothing in the loop heard that thought.

1. **`any-*` is a domain promise, not a backend-swap promise.** The prefix means the consumer stops
   caring about the whole domain. A backend swap is the most visible way to earn it; an ergonomic
   surface over one library earns it as well. `any-markdown`, `any-datetime`, `any-archive` are
   legitimate with one, two or zero third-party implementations underneath; the count is the detail
   the name promises you stop tracking.
2. **Names get more generic, never library-shaped** (upholds ADR 0008). Good: `any-markdown`,
   `any-datetime` (`timefmt` exists: check before minting a sibling). Bad: `markdown-it-extra` (origin
   library), `datetime-utils` ("utils" names nothing a consumer can want). Reading the name cold
   still decides.
3. **Fusing several libraries into one surface is the same move**: `kind = "composite"` (`convert-md`
   fuses docling/pandoc/markitdown/trafilatura). Nothing new in the ontology; wanting a better
   surface is now sufficient reason, where before only needing several backends was.

**Shape: promote the thing.** Where a domain has a thing, promote a type the consumer holds, which
owns its reading, laziness and derived values, not a drawer of functions each taking someone else's
type as argument 1 (a2kay's `links.py`: five call sites each hold a `re.Match`). E.g.
`doc = Markdown.from_path(p)`, `doc.wikilinks -> Sequence[WikiLink]`, `link.anchor/.name/.span`,
`doc.replace_wikilinks(fn) -> Markdown`.

- Accumulating methods on one coherent type is growth, not accretion. Constitution III governs dead
  code and duplication, not capability thinness; the kitchen-sink test at RECONCILE is *unrelated
  concerns fused*, not *many methods on one subject*.
- **Inherit almost never; wrap almost always.** Subclassing inherits breaking changes (`datetime`
  arithmetic on a subclass returns base `datetime`; an upstream field silently changes your type).
  Hold the library object as an attribute with an escape hatch (`.raw`, `.underlying`). Inherit only
  where the library is designed as a base class.

**Ambition and its guard.** The stated aim is a standard library for what a real app needs, reached
for before writing anything. The ADR 0006 guard stays load-bearing: **extracted, never invented**. An
ergonomics complaint counts only when you already wrote the awkward expression in a real app ("a
standard library would have an `any-csv`" is not a trigger). Breadth of subject and richness of
surface are licensed; provenance is not.

## Rejected

- **Reading three standing rules as bans.** They obscure the case rather than forbid it: ADR 0008 and
  0012's sizing rule (no `logging-extra`/`httpx-utils`) over-read as "improving one library is the
  disease"; constitution III and Article VIII over-read as anti-growth; `any-lib` glossed as "stop
  caring WHICH backend" with exemplars (`anyllm`, `anyembed`, `any-browser`) all having several
  backends, so a one-library domain looks like it has no `any-*`.
- **Seeding case (a2kay, 2026-09-18):** `src/a2kay/core/links.py`, 122 lines hand-rolling CommonMark
  fenced-block and inline-code range detection so `[[wikilink]]` inside a code span isn't a link. No
  markdown library is wrong; reading links with code spans excluded is just not a method on anything.

## Risk, accepted (most to least likely)

1. **Trivial wrappers**: a one-line delegation is not DEEP (constitution VI). Counterweight: adoption
   stays conservative, so a shallow piece shows up as an orphan at RECONCILE and is deleted; the cost
   is a demote, versus six lines rewritten in every app.
2. **Object-shape cargo-culting**: a class wrapping one function. Test: the type carries *state worth
   holding* (lazily-read body, parsed tree, cached derivation); stateless and single-purpose is a function.
3. **`any-*` inflation**: the prefix marks hard-won substrate-indifference (`anyllm`). Dilution is
   accepted deliberately: the prefix should mean "you stop caring about this domain".

## History

- 2026-09-18: decided. Trigger: a2kay's `links.py` above. Expires 2027-09-18 (re-justify once at
  least two `any-<domain>` pieces exist whose value is the surface rather than a backend swap; if
  every one is a thin restatement nobody adopted, the third trigger is manufacturing packages and
  should be cut). Track: governance / the promotion model.
