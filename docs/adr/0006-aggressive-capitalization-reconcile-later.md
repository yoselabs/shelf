---
id: 0006
title: Promote aggressively at writing time, reconcile later
statement: Generic substrate is promoted to the shelf when you write it, on a self-assessed "feels reusable"; adoption stays conservative and a mandatory reconcile pass prunes over-promotion.
concerns: [workflow]
status: accepted
decided_by: owner
updated: 2026-07-08
expires: 2027-01-08
distilled_into: agent-loop.md WORKFLOW: SEAM (PROMOTE direction) and WORKFLOW: RECONCILE
---

# 0006 — Aggressive capitalization: promote generic substrate at writing time, reconcile later

## Decision

The shelf's value is **not** shrinking software that exists; it is **reducing the custom code the
*next* project writes**. Target end-state: every app is mostly business logic plus dependencies; the
generic "jazz" (datetime/timezone handling, collection utils, FastAPI decorators, Pydantic custom
fields, pattern implementations and their safety wrappers, fillers for awkward library APIs,
supporting helpers) lives in shared shelf libraries. A promoted piece growing more universal is
growth that lives in the piece and never bloats a thin consumer (a2kay keeps calling
`complete(prompt)->str`).

- **Compare against the CATALOG, never another consumer.** While building you are usually unaware of
  other software being built; code-vs-catalog is the always-available frame.
- **Promote when you write it, not post-facto.** The moment you write a generic helper, pattern
  wrapper or abstraction over a weird API is the cheap moment; once wired into an app the chance is
  lost, and re-auditing old codebases is the real waste.
- **A self-assessed "this feels reusable" is enough.** No second consumer, no proof of reuse. The
  trigger is often friction: "this API is awkward, let me build the abstraction I wish existed."

Two guards stop aggression becoming a junk drawer:

1. **Shape-proven, not shape-guessed.** The consumer may be future; the shape may not be a guess
   (extracted, never invented). `convert_html(str, url)` is fine because a2web's real trafilatura
   calls prove its surface; inventing an interface no real code pressured is forbidden.
2. **Reconciliation is mandatory.** A recurring pass over the catalog: **merge** overlaps, **split** a
   kitchen-sink, **delete** the unused (Article VIII), **demote** an over-promotion. Lineage arcs
   (`absorbed-into`, `merged-with`, `supersedes`) record it. This is where "was this the right
   abstraction?" is answered, with hindsight rather than an upfront gate.

**Four directions at a seam** (choosing among them is the daily work):

1. **ADOPT**: a shelf piece fits as-is (DEEP·STABLE·WINS). Pin it, delete your copy.
2. **EVOLVE**: a piece almost fits; grow its contract to serve both cases rather than duplicate
   (`convert-md` gained `convert_html(str, url)`; `content-extract` composes on it), as long as the
   generalization stays coherent.
3. **PROMOTE**: nothing covers it and it is generic; capitalize it (shape-proven, now).
4. **DUPLICATE / SKIP**: evolving would distort the piece (two masters, kitchen-sink) or the need is
   too niche; keep it local. EVOLVE-vs-SKIP is a judgment, revisited at reconciliation.

**Why it self-corrects:** aggressive promote fills the catalog, conservative adopt (Article VI) forces
nothing onto anyone (born-`candidate` status plus opt-in tags absorb instability), and decay plus
reconciliation garbage-collect the over-production. What is expensive, losing the extraction moment,
is what is refused.

Propagated: doctrine #3/#4 and constitution VI/VII; `agent-loop.md` gains catalog-first
promote-in-the-moment and a RECONCILE step; the onboarding sweep (`runbooks/onboard-a-consumer.md`)
drops from primary mechanism to a post-facto catch-up for codebases that predate the shelf, with
per-candidate logic flipped to "promote every generic helper the catalog lacks".

Live cases: a2web's `llm_extract.Provider` is promoted (born `candidate`, a2kay keeps thin `anyllm`
and upgrades opt-in); a2web's generic utilities (settings loader, sqlite conditional-GET cache,
cookie-store matrix, collection/JSON helpers) are promoted while the fetcher's moat (block detection,
proxy routing, browser backends) stays; `convert-md` grows `convert_html(str, *, url)`.

## Rejected

- **Conservative gate: promote only when a second consumer pulls (rule of three), success measured by
  consumers shrinking.** The a2web sweep exposed it as the wrong objective: it concluded "adopt 0,
  promote 0, net delta ~0 = success" because promoting a2web's rich LLM Provider would grow `anyllm`
  and not shrink `a2kay`.

## Risk, accepted

Trades flexibility for reuse and will sometimes over-promote. The cost is paid down at reconciliation,
not avoided by a stricter front-end gate. If reconciliation is neglected the catalog rots; the pass is
the load-bearing other half.

## History

- 2026-07-08: decided. Supersedes the "rule-of-three / 2nd-consumer-pull" promotion gate from the
  bootstrap doctrine. Expires 2027-01-08 (re-justify, especially the reconciliation cost). Track:
  governance / the promotion model.
