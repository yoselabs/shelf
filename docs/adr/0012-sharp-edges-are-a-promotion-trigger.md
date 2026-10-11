---
id: 0012
title: Sharp edges are a promotion trigger
statement: A bug rooted in a dependency's behaviour is a promotion trigger fired at bugfix time; the lesson ships as a feature of a capability package, never as a library-shaped package.
concerns: [workflow]
status: accepted
decided_by: owner
updated: 2026-07-22
expires: 2028-01-22
distilled_into: agent-loop.md `WORKFLOW: SEAM` (second TRIGGER + the sharp-edge test in the PROMOTE direction)
---

# 0012 — Sharp edges are a promotion *trigger*, not just a promotion candidate

## Decision

The category was never missing (doctrine idea 4 and SEAM's trigger already name "an abstraction over
an awkward library API"); the **moment** was. Every existing trigger fires on "you are about to
write"; this class is discovered by chasing a bug, when it looks like a bugfix, not substrate. SEAM
gains a **second TRIGGER**, the bugfix moment, plus the sharp-edge test in PROMOTE.

A **sharp edge** is where a dependency (stdlib or third-party) is correct, documented and used
properly and a competent engineer still gets hurt. The one question, asked at bugfix time:

> **Did we learn this from a bug, or from the docs?** Docs: ordinary work, write it or fix upstream.
> Bug: reading harder would not have saved us; **the lesson is the asset**, so it belongs in the shelf.

Mechanical tell, greppable: **a production symbol whose only caller is a test** (a
`_reset_registry()`, a global that exists to be monkeypatched) is a sharp edge worked around, not solved.

Five recurring kinds (search patterns, not a taxonomy): **unsafe default** (`addHandler` appends
unconditionally; `Handler.handleError` writes a traceback to stderr, fatal on a stdio-protocol
server); **missing idempotence** (attach-handler, apply-schema, register-signal); **opaque failure**
(rich failure collapsed to one signal, so every consumer writes the same decoder; three vendors in
one sweep); **leaked substrate** (a driver writing to the inherited OS stderr fd); **no lifecycle**
(library assumes a short script, you run a server: idle reaping, non-daemon threads, teardown).

**Sizing rule:** a sharp edge is normally a *feature of a capability package*, not a package.
`add_handler`'s fix ships in a typed-events package, never `logging-utils`. If no capability package
can host it, ask what capability you are actually building; never create `<lib>-extra`. If the edge
belongs to something **we own** (a shelf package, an in-org framework), fix it there.

Economics: boilerplate is expensive to type and cheap to know; a sharp edge is the mirror image
(trivial code, expensive discovery), so what is amortized is the debugging.

## Rejected

- **Leaving it to the existing triggers.** Seeding case (a2web, 2026-07-22): `a2web.log.add_handler`
  grew `replace_existing=True` because `logging.getLogger()` is process-global while `build_app()`
  runs many times per process; each rebuild stacked another OTel handler, so the Nth build emitted N
  spans per event. No crash, only silently multiplied telemetry, found because a single-span test
  passed alone and failed in the full suite. No trigger fired and the lesson stayed in one repo.
- **Naming a package for the library it patches** (`logging-extra`, `httpx-extra`, `sqlite-utils`):
  ADR 0008's disease from the other direction; such packages attract anything adjacent.

## Risk, accepted

Over-firing: most bugs are our own logic. The trigger is specifically a bug whose root cause is a
*dependency's* behaviour; if one-line fixes for ordinary defects accumulate, tighten the trigger.

## History

- 2026-07-22: decided. Expires 2028-01-22 (re-justify once the bugfix trigger has fired from the loop
  in at least two consumers other than a2web; if it never fires it is unreachable and should be cut).
  Track: governance / the promotion model.
