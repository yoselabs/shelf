## Why

`convert-md`'s `documents` extra pulls in `docling` for PDF conversion. During
the a2web web-fetch substrate sweep this collided with `a2kit`'s `typer>=0.25`
pin inside the shared `shelf-a2web` workspace lock — the practical fix at the
time was to split heavy document engines (`docling`, `pandoc`, `markitdown`)
out of `convert-md`'s base into a separate package so the constraint only
enters a consumer's lock if they explicitly opt in.

That fix contains the blast radius but doesn't resolve the conflict, and it
was never verified against docling's *current* release — only reasoned about.
Two things need to happen before the shelf can call docling's role in PDF
conversion settled:

1. **Verify the conflict live**, against the docling version on PyPI today,
   not a remembered one.
2. **Verify docling is actually the right PDF engine**, on real (public
   domain, not user-supplied) PDFs, against the alternatives — we adopted it
   without a comparison test, on reputation.

## What Changes

- Live-verify (`uv add` in a throwaway project) whether `docling`/`docling-slim`
  still conflicts with `typer>=0.25`. **Already done during this proposal's
  authoring — see Decisions below; the conflict is confirmed, current, and
  structural** (not extra-gated). This proposal keeps that finding as the
  documented, dated evidence rather than a re-derived claim next time someone
  asks "is this still true?".
- Build a small, repeatable PDF-conversion comparison harness under
  `packages/convert-md/` (or a sibling `tests/comparison/` — TBD in design.md)
  that runs docling + N alternative engines over a public-domain PDF corpus
  and scores output on named fidelity axes (not just "looks fine").
- Decide, from the scored comparison: keep docling as the `documents`-extra
  PDF engine, replace it, or offer both behind a fidelity-tier choice.

## Capabilities

### New Capabilities
- `pdf-engine-comparison`: a maintained, re-runnable benchmark comparing PDF→markdown
  engines on fidelity, independent of any one consumer's opinion.

### Modified Capabilities
- `convert-md` (documents extra / sibling package): PDF engine selection becomes
  evidence-backed, with the conflict properly documented instead of assumed.

## Impact

- No consumer-facing break today — a2web already isolates the extra — but this
  is no longer purely shelf-internal due diligence: a2web has a dated, unbuilt
  backlog item ("PDF tier", `BACKLOG.md`, raised 2026-05-23) blocked on exactly
  this decision. This change **is** that decision, not a parallel one — a2web's
  own follow-up narrows to the tier-routing plumbing (content-type carve-out +
  extraction phase, mirroring `json-endpoint-direct-routing`), engine-agnostic,
  once this lands.
- Consequence for D3's decision rule: a2web resolves `typer==0.25.1` (from
  `a2kit`) today, and `docling-core`'s `typer<0.25` pin is unconditional — not
  extra-gated, not a soft preference to dodge. If docling wins the fidelity
  comparison on paper, a2web **cannot install it regardless** — the tax isn't a
  tiebreaker for a2web, it's a hard filter. Decision rule tightened accordingly:
  prefer best fidelity *among conflict-free candidates* for any consumer in
  a2web's position, rather than "best fidelity, tax discounted."
- Local-worth caveat: we don't yet know if a2web needs this badly enough to
  justify running the harness — that's still an open call, not decided by
  writing this down. The harness answers "which engine," not "is it worth it."
- If the comparison favors a different engine, a follow-up change swaps the
  PDF path in `convert-md`'s document engines and re-cuts a version.
