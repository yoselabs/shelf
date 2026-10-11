---
id: 0014
title: skill is a shelf Kind, distributed as a claude plugin
statement: Skills are a shelf Kind under the one shared loop, released by first-party claude plugin tooling from this repo; only push-based (auto-triggering) skills are catalogued.
concerns: [skills, packaging]
status: accepted
decided_by: owner
updated: 2026-10-10
expires: 2027-02-16
distilled_into: `agent-loop.md` `WORKFLOW: PROMOTE` step 3
---

# 0014 — `skill` is a shelf Kind; distributed as a `claude plugin`, gated by measured token cost

## Decision

Generalizing beyond Python packages was narrowed first: no second tech stack exists, so
stack-genericization is deferred with a trigger (first non-Python consumer). Package docs already
ride the package's tag and shelf doctrine is deliberately always-HEAD (not a Kind member), leaving
**skills** as the one real generalization. Four forks:

- **A, one loop.** `agent-loop.md`'s workflows (`SEAM`, `PROMOTE`, `RECEIVE`, `RECONCILE`, `BENCH`,
  `ESCAPE-HATCH`, `EVOLVE-THE-LOOP`) already reason generically over `Kind` (`config-preset`, ADR
  0004, is precedent). Only five mechanism slots are Kind-specific: unit dir, contract-verify tool,
  pin/release syntax, breaking-change signal, gate-membership test.
- **B, first-party `claude plugin` tooling.** `claude plugin eval` (resolves `plugin@marketplace`,
  runs a no-plugin baseline arm), `claude plugin tag` (validates `plugin.json` version against the
  marketplace entry before tagging; the skill Kind's "release = a git tag", enforced by the CLI),
  `claude plugin details` (the actual always-on token cost).
- **C, one repo, two roles.** The shelf repo is also the plugin marketplace and plugin source
  (`marketplace.json` points at a relative in-repo path, precedent: `context7-marketplace`), keeping
  one catalog projection, ledger, `just check` and resolver block.
- **D, two tiers.** `.agents/skills/` (shelf-internal tooling such as onboard-consumer, beads) is
  **pull-based**: invoked by path, absent from the auto-scanned listing even inside the shelf repo,
  zero standing cost. A catalog-registered plugin skill is **push-based**: auto-triggered by
  description, a real measured per-session cost. **`Kind: skill` governs only the push-based tier**;
  `.agents/skills/` stays outside the catalog.

Current rules (after the 2026-10-10 amendment):

- **Invocation mode is per skill.** `Kind: skill` means catalogued, plugin-distributed, evaled;
  whether it auto-triggers is each skill's choice, recorded in its catalog entry. A skill with
  `disable-model-invocation: true` leaves the always-on listing and runs only as `/name`;
  `claude plugin eval` still reaches it. Blueprint is user-invoked.
- **Evals** live in `shelf/evals/<name>/<case>/` (plugin root is the repo); results in
  `evals/results/`, gitignored.
- **Tags:** `claude plugin tag` tags the plugin as `skills--v<version>`; a skill's own release stays
  a shelf tag `<name>-vX.Y.Z`. Blueprint consumers record the checkpoint-set hash they were audited
  against, not a version.

Not decided: the numeric token-budget ceiling (deferred to the first real skill's `PROMOTE`, where
`claude plugin details` gives a number instead of a guess); converting any specific runbook (conversion
is earned by evidence); authoring `shelf-c2s`'s catalog/onboard skill.

## Rejected

- **A: a parallel `docs/skill-loop.md`.** Duplicates every workflow around the five slots and drifts;
  EVOLVE-THE-LOOP would have two files to keep current.
- **B: hand-rolled test harness and a `SKILL.md` description character-count cap.** Duplicates
  `claude plugin eval` and would not pass DEEP·STABLE·WINS; a proxy for a measurable fact is strictly
  worse than the fact (`claude plugin details`).
- **C: a second `shelf-skills` repo.** Multiplies every conflict-freedom mechanism for an independent
  release cadence nothing has asked for (Article VI: split only when something breaks without it).
- **D: one mechanism for all skills.** Would force `onboard-consumer` into an always-on listing, or
  deny a general-purpose skill the auto-discovery that is its point. Found mid-implementation:
  `shelf-n63` had already shipped `.agents/skills/onboard-consumer/`, verified in-session as absent
  from the scanned listing.

## History

- 2026-08-16: decided, forks A-D. Expires 2027-02-16 (re-justify at the half-year). Track: governance /
  catalog (see `docs/missions/onboarding-new-micro-software.md`).
- 2026-10-10 amendment (blueprint, the first real skill; `openspec/changes/blueprint-skill/`, design
  D14; measured on Claude Code 2.1.296 in a throwaway plugin):
  - Invocation mode became per skill. Dropped: fork D's tie of `Kind: skill` to push-based
    discovery. A user-invoked plugin skill is still catalogued and evaled, with zero standing cost,
    and a case with prompt `/probe hello` fired it and passed.
  - Eval location corrected by a real run: `claude plugin eval` refuses an eval dir inside `skills/`
    ("a loaded component directory"), through both `experimental.evals` and `--eval-dir`, so
    `experimental.evals: "skills"` was dropped for `evals/<name>/<case>/`.
  - Tag format recorded: `claude plugin tag` tags the plugin (`skills--v<version>`), not a skill.
