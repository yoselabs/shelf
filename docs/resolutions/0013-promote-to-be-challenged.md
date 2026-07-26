# 0013 — Promote to be challenged: verifiability is not a promotion gate

- **Status:** decided (2026-07-26)
- **Expires:** 2028-01-26 (re-justify once a piece promoted *under acknowledged shape-uncertainty* has been bent by a second consumer at least twice — if early promotion only ever produced churn and never a real generalization, the asymmetry below is wrong and this resolution should be cut)
- **Track:** governance / the promotion model
- **Distilled into:** agent-loop.md `WORKFLOW: SEAM` (the PROMOTE direction gains the "verifiability is not a gate" clause + the verification-travels-with-the-code rule; the ADOPT/EVOLVE directions gain "the second consumer is the abstraction's first challenge")

## The fork

Resolution 0006 already says *capitalize aggressively, reconcile later* — the
posture is `promote, not defer`. So on paper this class was covered. It still
was not reaching the shelf on time, and the reason is a **second, quieter gate**
that 0006 never named: *"it isn't proven yet — hold it until it is."*

The two look identical from inside the session and are completely different:

- 0006's deferral is laziness — "I'll promote it later." The fix is a posture.
- This deferral is *conscientiousness* — "I can't yet verify this is the right
  shape / can't yet fully test it, so it would be irresponsible to publish it."

The second one feels like good engineering. It is the more dangerous of the two,
because it is *reasoned*, and the reasoning is wrong in a specific way.

## The seeding case (a2web browser backends, 2026-07-26)

a2web built a two-rung browser abstraction (a Playwright-API rung + a raw-CDP
rung behind one `BrowserBackend` Protocol). A verification-provenance review
argued: **hold the drivers off the shelf** until a shelf-side real-launch gate
exists, because a promoted driver with only a hand-written fake + a
skip-on-missing-binary smoke ships to other consumers *without a foreign witness*
— and that is exactly how a2web's own robust rung sat dead-on-launch while green.

That caution was right about the danger and wrong about the remedy. It
**conflated two independent axes**:

```
axis A — is the SHAPE right?        (is BrowserBackend the universal seam, or a2web-fit?)
axis B — is it VERIFIED?            (does a real launch actually render?)
```

and it used axis B to gate promotion. But:

- Axis A is *not* resolved by holding. It is resolved by a **second consumer**
  adopting the Protocol and finding out where it is a2web-shaped rather than
  universal. Holding the drivers guarantees axis A never gets challenged — the
  seam stays frozen at a2web's local optimum, and the *first* other consumer
  inherits a2web's blind spots wholesale instead of correcting them.
- Axis B does not need holding either. Verification is not a *precondition* of
  promotion; it is an **obligation that travels with the code** — you port the
  real-launch lane into the shelf's CI *in the same promotion*. The witness
  arrives with the artifact, not before it.

So the correct move is: **promote the drivers now, and carry the real-launch gate
with them.** Both axes served, neither used to postpone.

## The rule

> **Verifiability and shape-certainty are not promotion gates.** Promote the real
> substrate you built even when you cannot yet prove it is the final shape and
> cannot yet fully test it — *because* those are exactly the things a second
> consumer's adoption fixes, and it can only fix what is already on the shelf.

The mechanism this protects is the shelf's actual evolution engine:

> **The second consumer is the abstraction's first real challenge.** A piece that
> fit its origin app perfectly is *over-fit* until something else bends it. The
> bend — generalize / simplify / make universal (the EVOLVE direction) — is the
> event that turns origin-app scaffolding into shared substrate. Postponing
> promotion "until the shape feels right" forfeits the one event that would have
> told you what right *is*.

And its companion obligation, so "not a gate" never decays into "no witness":

> **Verification travels with the promotion.** If a piece needs a real-substrate
> lane to be trustworthy (a browser launch, a container boot, a live call), that
> lane ships *in the same change* as the code — ported into the shelf's own CI,
> not left as a promise. "Promote without the gate" and "promote with the gate
> ported alongside" are different acts; only the second is this rule.

## The asymmetry that makes it safe

Early promotion under uncertainty is only correct because the shelf already makes
a wrong guess cheap, and nothing makes a forfeited challenge cheap:

```
wrong early promotion   → RECONCILE demotes it (duplicate back into its one
                          consumer, retire the package). Tags stay immutable;
                          an evolution ships as a NEW tag, the old one never
                          breaks a pinner. Bounded, expected, cheap-to-undo.
forfeited challenge     → the abstraction never learns it was over-fit. The
                          first other consumer inherits the blind spot instead
                          of correcting it. Not recoverable on the same timeline.
```

Bounded downside against unbounded-upside. That asymmetry *is* the argument — it
is not "promote everything," it is "when unsure, the uncertainty is a reason to
promote *sooner* so it gets challenged, never a reason to hold."

## The boundary kept (so this can't rationalize dumping)

"Promote to be challenged" licenses uncertainty about **shape** and
**verification**. It licenses nothing else. The two SEAM guards stand unchanged:

- **Extracted** — real code your app actually needs and runs, never a speculative
  empty abstraction promoted "in case." Guessing at the *shape* of code you built
  is the rule; guessing that a need exists is not.
- **Generic** — substrate, not your product moat.

## The risk, named

The failure mode is **"promote it and walk away."** This resolution makes it
easy to publish something half-shaped and call the incompleteness a virtue. Two
tells that you have crossed the line:

1. **The verification lane never lands.** You promoted the drivers and the
   real-launch gate stayed a TODO. That is not this rule — that is shipping a
   blind spot to every consumer. The obligation is not a gate, but it is real:
   same change, or you did not do it.
2. **No second consumer is even plausible.** "Promote to be challenged" assumes a
   challenger will come. If nothing but the origin app will ever touch it, there
   is no challenge to earn — that is a DUPLICATE/SKIP, revisited at RECONCILE, not
   a promotion.

Third, the honest cost: some early promotions *will* be wrong, and RECONCILE will
demote them. That is the price of the challenge mechanism, paid in the currency
the shelf chose to be cheap (a demote), not the currency it cannot get back (a
forfeited first challenge). If demotes start outnumbering the generalizations they
were supposed to buy, it is the *plausible-second-consumer* guard that needs
tightening — not this posture.
