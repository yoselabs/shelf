# 0014 — `skill` is a shelf Kind; distributed as a `claude plugin`, gated by measured token cost

- **Status:** decided (2026-08-16)
- **Expires:** 2027-02-16 (re-justify at the half-year)
- **Track:** governance / catalog (see `docs/missions/onboarding-new-micro-software.md`)
- **Distilled into:** `agent-loop.md` `WORKFLOW: PROMOTE` step 3

## The fork

Generalizing the shelf beyond Python packages was raised as a broad question — tech stacks, skills,
runbooks, doc formats all at once (exploration, 2026-08-16). Narrowed first: no second tech stack
exists, so stack-genericization is deferred with an explicit trigger (first non-Python consumer),
not built. Doc formats split cleanly — package docs already ride the package's tag, shelf doctrine is
deliberately always-HEAD (not a Kind member), leaving **skills** as the one real generalization with
no answer yet.

Four sub-forks needed deciding, not just one:

**Fork A — one loop or two?** A parallel `docs/skill-loop.md`, vs one file with per-Kind mechanism
slots.

**Fork B — how is a skill's contract verified, pinned, and distributed?** Hand-rolled tooling, vs
first-party `claude plugin` subcommands (`eval`, `tag`, `details`, marketplace install/update).

**Fork C — one repo or two?** A second `shelf-skills` repo for independent release cadence, vs the
existing shelf repo doubling as its own `claude plugin` marketplace and plugin source.

**Fork D — one skill-distribution mechanism, or two tiers?** Route every skill (including
shelf-process-internal tooling) through the same mechanism, vs recognizing that pull-based
(`.agents/skills/`, invoked by path) and push-based (auto-scanned, catalog-registered) skills have
opposite cost/discoverability trade-offs and need different mechanisms.

## Decision

**A — one loop.** `docs/agent-loop.md`'s workflows (`SEAM`, `PROMOTE`, `RECEIVE`, `RECONCILE`,
`BENCH`, `ESCAPE-HATCH`, `EVOLVE-THE-LOOP`) already reason generically over `Kind` — `config-preset`
(resolution 0004) is precedent that Kind membership isn't defined by "is a Python package." Only five
mechanism slots are Kind-specific per member (unit dir, contract-verify tool, pin/release syntax,
breaking-change signal, gate-membership test); a second loop file would duplicate every workflow
around those slots and *will* drift — `EVOLVE-THE-LOOP` already has one file to keep current with its
own resolutions, and a second file doubles that surface for a benefit (per-Kind loop steps) that the
slots already capture without it.

**B — first-party `claude plugin` tooling, not hand-rolled.** `claude plugin eval` already resolves
`plugin@marketplace` ids and runs a no-plugin baseline arm — a bespoke test harness against `SKILL.md`
prose would duplicate it for no reason the constitution's DEEP·STABLE·WINS gate would pass. `claude
plugin tag` already validates `plugin.json`'s version against the marketplace entry before creating
the release tag — the skill Kind's answer to "release = a git tag," enforced by the CLI, not
discipline. `claude plugin details <name>` reports the actual always-on token cost the harness
computes; an earlier draft of this decision considered a hand-rolled `SKILL.md` description
character-count cap as a proxy — rejected once `claude plugin details` was found, since a proxy for a
measurable fact is strictly worse than the fact itself.

**C — one repo, two roles.** Confirmed working precedent on this machine: `context7-marketplace`'s
`marketplace.json` points a plugin at a relative in-repo path — no second repo required. A second
`shelf-skills` repo would multiply every conflict-freedom mechanism the constitution gives one repo
(one catalog projection, one ledger, one `make check`, one resolver block) for independent release
cadence, which nothing has asked for (Article VI: split only when something demonstrably breaks
without it).

**D — two tiers, not one mechanism.** Discovered mid-implementation, not designed up front:
`shelf-n63` had already shipped `.agents/skills/onboard-consumer/`, invoked by path from
`$SHELF_HOME`, before this resolution was written. Verified directly in-session: content under
`.agents/skills/` does not appear in a session's auto-scanned skill listing, even working inside the
shelf repo itself — it is **pull-based** (an agent must already be told to look there; zero standing
cost) where a catalog-registered, plugin-installed skill is **push-based** (auto-triggered by
description match; a real, measured per-session cost). These are opposite trade-offs serving
different audiences — shelf-process-internal tooling (onboard-consumer, beads) wants zero standing
cost and doesn't need to fire in an unrelated consumer session; a general-purpose skill wants to be
found without an agent already knowing where to look, and that discoverability is exactly what costs
tokens. Collapsing them into one mechanism would either force `onboard-consumer` into an always-on
listing it has no business occupying, or deny a general-purpose skill the auto-discovery that is its
entire point. **`Kind: skill` in the catalog governs only the push-based tier.** `.agents/skills/`
stays outside the catalog, ungoverned by this resolution, exactly as `shelf-n63` already built it.

## What this does not decide

The numeric token-budget ceiling (per-skill or shelf-wide) — deferred to the first real skill's
`PROMOTE`, where `claude plugin details` gives a concrete number instead of a guess made with zero
skills on the shelf. Also out of scope: converting any specific existing runbook (the earned-gate
requirement only says conversion needs evidence, not which runbooks currently qualify), and
authoring `shelf-c2s`'s catalog/onboard skill (a downstream consumer of this contract, not part of
deciding it).
