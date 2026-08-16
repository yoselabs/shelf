## Context

See `proposal.md` for motivation. Relevant current state:

- `docs/agent-loop.md`'s workflows (`SEAM`, `PROMOTE`, `RECEIVE`, `RECONCILE`, `BENCH`,
  `ESCAPE-HATCH`, `EVOLVE-THE-LOOP`) already reason generically over `Kind`; only five slots are
  Python-specific per Kind today (unit dir, contract-verify tool, pin syntax, breaking-change signal,
  gate-membership test).
- `Kind` already has one non-Python member (`config-preset`, resolution 0004) — precedent that
  membership isn't defined by "is a Python package."
- The shelf's own machine has a working precedent for a marketplace living in a distribution-neutral
  repo (`context7-marketplace`'s `marketplace.json` points a plugin at a relative in-repo path,
  `"./plugins/claude/context7"`), and for a personal multi-plugin marketplace with per-plugin
  versioning (`iorlas-marketplace`).
- `claude plugin` ships first-party subcommands that map directly onto shelf mechanics already:
  `tag` (git tag validated against `plugin.json`/`marketplace.json` agreement), `update` (pull, not
  hot-reload — "restart required to apply"), `details` (exact always-on/on-invoke token cost per
  component).
- `shelf-n63` (`openspec/changes/onboard-consumer-skill/`) merged to `main` before this change was
  applied, shipping `.agents/skills/onboard-consumer/` — invoked by path from `$SHELF_HOME`, not
  through any Claude Code plugin mechanism. Verified directly in-session: `.agents/skills/beads/`
  (present in this very repo) does not appear in a session's auto-scanned skill listing even when
  working inside the shelf repo — `.agents/skills/` is pull-based (an agent must already be told to
  look there), not push-based (auto-triggered by description match). This is a materially different
  distribution answer than this change's original draft assumed (see Decisions, "Two skill tiers").

## Goals / Non-Goals

**Goals:**
- Give a skill member the same five answered mechanism slots a package member already has.
- Make the token-budget constraint enforceable by a tool call, not a style note.
- Let the shelf distribute skills without inventing a second repo or a second loop.

**Non-Goals:**
- Not deciding the actual numeric token budget for any specific skill — that's each skill's own
  `PROMOTE`, informed by `claude plugin details`.
- Not authoring `shelf-n63`'s or `shelf-c2s`'s skill content.
- Not generalizing packages to a second tech stack (no second stack exists; deferred separately).
- Not converting any existing runbook — this change only adds the gate that future conversions must
  pass.

## Decisions

**Two skill tiers, not one mechanism covering both.**
Alternative considered (this change's original draft, before `shelf-n63`'s outcome was checked
against it): route every skill — including shelf-process-internal tooling like `onboard-consumer` —
through the `claude plugin` marketplace mechanism, for one uniform answer. Rejected on discovery that
`onboard-consumer` already ships, working, on the opposite mechanism (pull-based, zero standing
cost), and that forcing it onto the plugin/marketplace path would add a real cost (an always-on
listing entry) for a skill that has no business auto-firing in an unrelated consumer session — nobody
wants `onboard-consumer`'s trigger phrasing competing for attention in a session about something else
entirely. The two mechanisms have genuinely opposite cost/discoverability trade-offs (pull-based:
zero cost, but unreachable without prior knowledge of the path; push-based: real per-session cost,
but auto-triggers without an agent needing to know it exists first) — collapsing them into one loses
the property that makes each correct for its job. `Kind: skill` in this change's contract therefore
scopes explicitly to the push-based, catalog-registered, general-purpose tier; `.agents/skills/`
stays outside the catalog entirely, ungoverned by this contract, exactly as it already works.

**One loop, per-Kind mechanism slots — not a second loop file.**
Alternative considered: a parallel `docs/skill-loop.md`. Rejected — `EVOLVE-THE-LOOP` already has to
keep one file in sync with its own resolutions; a second loop file doubles that maintenance surface
and *will* drift (one gets updated, the other doesn't, discovered only when an agent follows the
stale one). The five mechanism slots differ by Kind; the workflows around them (when to adopt, when
to promote, how to reconcile) do not, so they stay in the one file `agent-loop.md` already is.

**Skill contract-verify is `claude plugin eval`, not a bespoke test harness.**
Alternative considered: hand-write assertions against `SKILL.md` prose. Rejected — `claude plugin
eval` already exists, already resolves `plugin@marketplace` ids, and already runs a no-plugin
baseline arm for comparison. Building a parallel harness would duplicate first-party tooling for no
reason the constitution's "adopt conservatively, DEEP·STABLE·WINS" gate would pass.

**Token budget is asserted via `claude plugin details`, not a hand-rolled char-count heuristic.**
An earlier exploration in this session considered a `SKILL.md` description length cap (chars) as the
enforcement mechanism. `claude plugin details <name>` supersedes it — it reports the actual always-on
token figure the harness computes, not a proxy for it. The catalog entry records this measured
figure; drift is caught at `RECONCILE`, not guessed at write time.

**Distribution: one repo is both marketplace and plugin — not a second `shelf-skills` repo.**
Confirmed a same-repo marketplace+plugin pattern already works (`context7-marketplace`). A second
repo would multiply every conflict-freedom mechanism the constitution already gives one repo (one
catalog projection, one ledger, one `make check`, one resolver block) for a benefit — independent
release cadence — nothing has asked for yet (constitution Article VI: adopt/split only when something
demonstrably breaks without it).

**Updates are pull-at-checkpoint, matching `SESSION-RESOLVE`/`RECEIVE` — not hot-reload.**
`claude plugin update` itself states "restart required to apply," so there was no live alternative to
reject here; the design decision is *where* in the loop that pull happens (at `SESSION-RESOLVE`'s
staleness-bound checkpoint, exactly where a package pull already happens) rather than inventing a
separate skill-specific cadence.

**Runbook→skill conversion requires evidence, enforced as a `PROMOTE` requirement — not left as
prose guidance.**
Article V ("protection is earned") already covers this in spirit for contracts; making it an explicit
requirement under `SEAM`/`PROMOTE` (rather than trusting an agent to apply Article V by analogy) is
consistent with why `agent-loop.md` exists at all — structure over discipline, not memory.

## Risks / Trade-offs

**[Risk] `claude plugin eval` may not fully cover non-deterministic or judgment-heavy skills** (e.g. a
skill whose "correctness" is stylistic, like brainstorming coaching) → **Mitigation**: the
gate-membership test only requires eval *coverage exists*, not a specific pass bar; a skill's own
`PROMOTE` sets what "passing" means for that skill, same as packages choose their own test depth.

**[Risk] The token-budget figure drifts between `PROMOTE`s as Claude Code's own tokenizer/format
changes** → **Mitigation**: `RECONCILE`'s re-check (already a requirement above) catches this with
hindsight, the same mechanism that catches an over-promoted package; it's not a one-time gate.

**[Risk] No second stack means the `skill` Kind is the first real test of "is a mechanism slot
actually Kind-generic," and it might reveal the loop has more Python-specific assumptions than the
five identified slots** → **Mitigation**: `EVOLVE-THE-LOOP` exists exactly for this — friction
discovered while building the first real skill member becomes a fast-follow resolution, not a reason
to block this change on solving every possible future Kind up front.

## Migration Plan

No data migration — this is new schema surface (`kind = "skill"` as an additional enum value) plus
new scaffold files. Existing `packages/*` catalog entries, use-cases, and ledger rows are untouched.
Rollback is deleting the scaffold and the resolution; nothing depends on it yet since no skill member
exists.

## Open Questions

- The numeric token-budget ceiling itself (per-skill and shelf-wide aggregate) — deferred to the
  first real skill's `PROMOTE`, where `claude plugin details` gives a concrete number to react to
  instead of a guess made now with zero skills on the shelf.
