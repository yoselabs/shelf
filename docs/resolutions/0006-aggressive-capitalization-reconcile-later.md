# 0006 — Aggressive capitalization: promote generic substrate at writing time, reconcile later

- **Status:** decided (2026-07-08) — supersedes the "rule-of-three / 2nd-consumer-pull" promotion gate.
- **Expires:** 2027-01-08 (re-justify at the half-year — especially the reconciliation cost)
- **Track:** governance / the promotion model

## The correction

The bootstrap doctrine made promotion **conservative**: a piece graduated only when a *second* consumer
pulled it (rule-of-three), and success was measured by *existing consumers shrinking*. The a2web sweep
exposed this as the wrong objective function — it concluded "adopt 0, promote 0, net delta ~0 = success"
because promoting a2web's rich LLM Provider would *grow* `anyllm` and not shrink `a2kay`.

That is backwards. The shelf's value is **not** shrinking software that already exists. It is **reducing
the custom code the *next* project has to write** by capitalizing proven substrate into shared, ownable
libraries. Generalizing a helper *should* make its micro-software larger and less single-case-catered —
that growth is "more universal," it lives in the piece, and it never bloats a thin consumer (a2kay keeps
calling `complete(prompt)->str`; the richer surface is merely *available*).

## The model

**Target end-state:** every app is *mostly business logic + dependencies*. The generic "jazz" —
datetime/timezone handling, timedelta math, collection utils (chunking), FastAPI decorators, Pydantic
custom fields, pattern implementations *and their safety wrappers*, fillers for awkward stdlib/library
APIs, a service's supporting helper functions — belongs in shared shelf libraries, not copy-pasted inline.

**Promotion is aggressive, and happens at writing time:**

- **Compare against the CATALOG, never against another consumer.** While building any software you are
  usually unaware of other software being built, so consumer-vs-consumer is the wrong, unavailable frame.
  Code-vs-shelf-catalog is the right, always-available one.
- **Promote when you write it, not post-facto.** The moment you write a generic helper, a pattern
  wrapper, or an abstraction over a weird API, that is the cheap moment to home it in the shelf. Once it
  is wired into an app the chance is lost, and re-auditing old codebases to extract it is the real waste
  of tokens and time.
- **A self-assessed "this feels reusable" is enough.** No second consumer required; no proof of reuse
  required. Speculate a little. The trigger is often *friction*: "this stdlib/library API is awkward, let
  me build the abstraction I wish existed."

**The two guards that keep aggression from becoming a junk drawer:**

1. **Extracted, never invented.** You only promote code a real app actually needed (n=1 *real use*). You
   never publish an empty package to look complete. This is the surviving thread of the old
   "promotion, not publication" — the code is always used; only its *future* reuse is speculative.
2. **Reconciliation is mandatory.** A recurring, deliberate pass over the catalog: **merge** overlapping
   packages, **split** a kitchen-sink, **delete** the unused (Article VIII decay), **demote / duplicate
   back** an over-promotion. This is where "was this the right abstraction?" gets answered — *with
   hindsight, not by an upfront gate*. Lineage arcs (`absorbed-into`, `merged-with`, `supersedes`)
   record it.

## Why this is self-correcting (the answer to "how do we find the balance?")

You do **not** find the flexibility-vs-promotion balance by guessing at write time. You find it
empirically at **reconcile** time. The system self-corrects because three postures compose:

- **Aggressive promote** fills the catalog with proven generic substrate.
- **Conservative adopt** is unchanged — a consumer still pulls a dep only on DEEP·STABLE·WINS (Article VI),
  so nothing is *forced* onto anyone, and instability is absorbed by born-`candidate` status + opt-in tags.
- **Mandatory decay + reconciliation** garbage-collect whatever the catalog over-produced.

Aggressive intake, judicious adoption, disciplined pruning. The catalog is allowed to over-produce because
decay is cheap and extraction-at-writing-time is cheap; what is expensive — losing the extraction moment —
is the thing we now refuse to lose.

## What changes (propagated)

- **Doctrine** #3/#4 and **constitution** VI/VII: promote aggressively (extracted + generic + reconciled),
  not on a 2nd-consumer gate. Adopt stays conservative.
- **agent-loop.md**: the standing loop gains **catalog-first, promote-in-the-moment** behavior and a
  **RECONCILE** step; nominate-vs-promote is recast (promote is now the cheap default for generic substrate).
- **The onboarding sweep** (`runbooks/onboard-a-consumer.md`) is demoted from *primary mechanism* to a
  **post-facto catch-up** for codebases that predate the shelf (like a2web/a2kay) — and its per-candidate
  logic flips: promote every generic helper the catalog lacks, regardless of cross-consumer overlap.

## Consequence for the live cases

- **a2web's `llm_extract.Provider`** → **promote** (async structured completion + cost accounting is deep,
  coherent, universal). Born `candidate`; a2kay keeps its thin `anyllm` tier and upgrades opt-in if ever.
- **a2web's generic utilities** (env/YAML settings loader, sqlite conditional-GET cache shell,
  cookie-store matrix, collection/JSON helpers) → **promote** the generic ones; leave the fetcher's
  product moat (block detection, proxy routing, browser backends) in a2web.
- **convert-md** grows a `convert_html(str, *, url)` capability — a real friction-driven abstraction.

## The risk, named

This trades some flexibility for reuse, and it will sometimes over-promote. That cost is **accepted** and
**paid down at reconciliation**, not avoided by a stricter front-end gate. If reconciliation is neglected,
the catalog rots — so the reconciliation pass is not optional garnish; it is the load-bearing other half.
