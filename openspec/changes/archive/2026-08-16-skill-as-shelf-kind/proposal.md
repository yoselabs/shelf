## Why

Denis wants the shelf to cover skills (Claude Code's judgment-layer artifacts) alongside Python
packages — triggered by `shelf-n63`/`shelf-c2s` about to author actual skills with no shelf contract
to conform to yet, and by a real, measured constraint: a skill is a permanent per-session token tax
(`claude plugin details <name>` prints it exactly) paid by every consumer that installs it, whether
or not it fires. Explored and measured this session (57 installed skills already cost ~5,480 tokens
of fixed per-session overhead); this proposal formalizes what was decided, not re-derives it.

The loop (`docs/agent-loop.md`) already reasons about `Kind` generically — `config-preset`
(resolution 0004) is precedent that `Kind` isn't only "Python package." What's missing is the
skill-specific answer to the five mechanism slots every Kind needs (unit dir, contract-verify, pin,
breaking-change signal, gate-membership test) and the shelf's own distribution surface for shipping
them. Without this, the next skill either invents its own ad hoc contract or ships with no contract
at all — the same silent-loss shape `test_gate_covers_every_package.py` and
`test_catalog_release_is_current.py` were written to catch for packages.

**This governs one of two skill tiers, not both.** `shelf-n63` (merged to `main` before this change
was applied) already shipped `.agents/skills/onboard-consumer/`, invoked by path from
`$SHELF_HOME` — zero standing token cost, but only reachable by an agent already told to look there
(the same pull-based mechanism `agent-loop.md` itself uses). Verified directly: `.agents/skills/`
content does not appear in a session's auto-scanned skill listing even when working inside the shelf
repo itself. That tier is right for shelf-process-internal tooling and is untouched by this change.
This change governs the *other* tier — a general-purpose, catalog-registered `Kind: skill` meant to
auto-trigger in a **consumer's own, unrelated** sessions, which is only reachable through Claude
Code's push-based discovery (an installed plugin's `skills/` dir or `~/.claude/skills`) — the
mechanism the token-budget constraint actually applies to, since a pull-based skill has no standing
cost to budget.

## What Changes

- Add `skill` as a documented `Kind` (alongside `primitive | any-lib | composite | cli | framework |
  config-preset`) with its own answers to the five mechanism slots:
  - unit dir: `skills/<name>/` (parallel to `packages/<name>/`), `SKILL.md` frontmatter = the contract
  - contract-verify: `claude plugin eval` (the skill analogue of `pytest`/`make check`)
  - pin/release: `claude plugin tag` (git tag `<name>--vX.Y.Z`, validated against `plugin.json`)
  - breaking-change signal: same `CHANGELOG.md` arrow-notation convention packages already use
  - gate-membership test: a new assertion (mirroring `test_gate_covers_every_package.py`) that every
    `skills/*/` entry is covered by an eval, not just present
- Add a **token-budget requirement** to the skill contract: `claude plugin details <name>`'s
  always-on token count is checked and asserted at `PROMOTE` and `RECONCILE`, the same posture
  `make check` already has over packages. No numeric ceiling is fixed by this change — the assertion
  wires up the gate; the number is a judgment call the first real skill's `PROMOTE` will set.
- Turn the shelf repo into its own `claude plugin` marketplace **and** plugin source in one repo
  (`.claude-plugin/marketplace.json` + `plugin.json` + `skills/`), scaffolded but empty — no skill
  content is authored by this change. Consumers add it via `claude plugin marketplace add` +
  `claude plugin install`; updates are pull-at-checkpoint (`claude plugin marketplace update` +
  `claude plugin update`, "restart required to apply"), mapped onto the loop's existing
  `SESSION-RESOLVE` staleness bound and `RECEIVE` opt-in-upgrade posture — no new upgrade philosophy.
- Extend `WORKFLOW: SEAM`'s `PROMOTE` direction with an explicit **earned-conversion gate** for
  runbook→skill promotion: a runbook only becomes a skill once a live agent has demonstrably missed
  it (Article V's "protection is earned" test, applied to skill triggers) — never a blanket sweep.
  No specific runbook is converted by this change.
- One-line addition to `docs/glossary.md`'s `Kind` enum (skill joins the list, same treatment as
  `config-preset` got — no new glossary concept, just a new enumerated value).
- A `docs/resolutions/0014-skill-is-a-shelf-kind.md` capturing the alternatives rejected (a second
  loop file for skills; a separate shelf-skills repo; blanket runbook conversion) with the
  distillation landing in `agent-loop.md` in this same change, per `EVOLVE-THE-LOOP`'s own rule.

**Out of scope** (explicitly, so this doesn't creep): multi-stack genericization for packages (no
second stack exists — deferred, no bead needed unless requested); authoring any actual skill content,
including `shelf-c2s`'s catalog/onboard skill (a downstream consumer of this contract, not part of
it); converting any specific existing runbook; changing anything about `.agents/skills/` or
`onboard-consumer` — that tier already works and is not this change's concern.

## Capabilities

### New Capabilities
- `skill-kind`: the shelf's `Kind: skill` contract — catalog schema fields, the five mechanism-slot
  answers, and the token-budget assertion a skill member must satisfy.
- `shelf-plugin-distribution`: the shelf repo as both a `claude plugin` marketplace and plugin
  source — scaffold shape, install/update mapped onto `SESSION-RESOLVE`/`RECEIVE`, `claude plugin
  tag` as the release mechanism.

### Modified Capabilities
- `agent-loop-workflows`: `WORKFLOW: SEAM`'s `PROMOTE` direction gains the earned-conversion gate for
  runbook→skill promotion (a new requirement, not a rewrite of the existing four directions).

## Impact

- `docs/glossary.md` — one-line `Kind` enum addition.
- `docs/agent-loop.md` — `SEAM`/`PROMOTE` gains the earned-conversion requirement; no other workflow
  changes (they're already Kind-agnostic).
- `tools/catalog.py`, `catalog/README.md` — schema/projection accepts `kind = "skill"` entries (no
  new fields beyond what packages already carry: name, kind, tier, release, capability,
  implementation, status, owner, notes).
- New: `.claude-plugin/marketplace.json`, `plugin.json`, `skills/.gitkeep` at shelf root (scaffold
  only).
- New: `docs/resolutions/0014-skill-is-a-shelf-kind.md`.
- New: a gate-coverage test for `skills/*/` (mirrors `tests/test_gate_covers_every_package.py`) and a
  token-budget assertion (mirrors `tests/test_catalog_release_is_current.py`'s "hand-maintained fact
  checked against the tool that knows it" shape).
- No package code changes; no consumer repo (a2kay, a2web) changes.
