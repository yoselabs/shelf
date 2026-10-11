---
id: 0013
title: Promote to be challenged
statement: Unproven shape and unfinished verification are not reasons to hold a promotion; promote real substrate so a second consumer can challenge it, and ship its verification lane in the same change.
concerns: [workflow]
status: accepted
decided_by: owner
updated: 2026-07-26
expires: 2028-01-26
distilled_into: agent-loop.md `WORKFLOW: SEAM` (PROMOTE gains the "verifiability is not a gate" clause and the verification-travels-with-the-code rule; ADOPT/EVOLVE gain "the second consumer is the abstraction's first challenge")
---

# 0013 — Promote to be challenged: verifiability is not a promotion gate

## Decision

> Verifiability and shape-certainty are not promotion gates. Promote the real substrate you built
> even when you cannot yet prove it is the final shape or fully test it, because a second consumer's
> adoption fixes exactly that, and it can only fix what is already on the shelf.

- **The second consumer is the abstraction's first real challenge.** A piece that fit its origin app
  perfectly is *over-fit* until something else bends it; the bend (generalize, simplify, EVOLVE) is
  what turns origin scaffolding into shared substrate. Holding "until the shape feels right"
  forfeits the one event that would say what right is.
- **Verification travels with the promotion.** If a piece needs a real-substrate lane (browser
  launch, container boot, live call), that lane ships *in the same change*, ported into the shelf's
  CI. "Promote without the gate" and "promote with the gate ported alongside" are different acts.
- **Why safe (asymmetry).** Wrong early promotion: RECONCILE demotes it (duplicate back into its one
  consumer, retire the package); tags are immutable and evolution ships as a NEW tag, so no pinner
  breaks. Bounded and cheap. Forfeited challenge: the abstraction never learns it was over-fit and the
  first other consumer inherits the blind spot. Not recoverable on the same timeline. When unsure,
  promote *sooner*.
- **Boundary kept.** Only shape and verification may be uncertain. **Extracted** (real code your app
  needs and runs, never a speculative empty abstraction) and **Generic** (substrate, not product moat)
  stand unchanged.

## Rejected

- **"It isn't proven yet, hold it until it is."** ADR 0006 named the lazy deferral; this is the
  *conscientious* one, more dangerous because it is reasoned. Seeding case (a2web browser backends,
  2026-07-26): a two-rung abstraction (Playwright-API rung + raw-CDP rung behind one
  `BrowserBackend` Protocol). A review argued to hold the drivers until a shelf-side real-launch gate
  exists, since a promoted driver with only a fake and a skip-on-missing-binary smoke ships without a
  foreign witness (how a2web's robust rung sat dead-on-launch while green). Right about the danger,
  wrong remedy: it conflated axis A (is the SHAPE right?) with axis B (is it VERIFIED?) and gated
  promotion on B. A is resolved only by a second consumer, never by holding; B is an obligation that
  travels with the code. So: promote the drivers now and carry the real-launch gate with them.

## Risk, accepted

The failure mode is **"promote it and walk away"**. Tells: (1) the verification lane never lands (that
is shipping a blind spot, not this rule); (2) no second consumer is even plausible, which is a
DUPLICATE/SKIP revisited at RECONCILE, not a promotion. Some early promotions will be wrong and
RECONCILE will demote them; that is the price, paid in the cheap currency (a demote). If demotes
outnumber the generalizations they buy, tighten the plausible-second-consumer guard, not this posture.

## History

- 2026-07-26: decided, extending ADR 0006 (which named only the lazy deferral). Trigger: the a2web
  browser-backends review above. Expires 2028-01-26 (re-justify once a piece promoted under
  acknowledged shape-uncertainty has been bent by a second consumer at least twice; if early
  promotion only produced churn, the asymmetry is wrong and this should be cut). Track: governance /
  the promotion model.
