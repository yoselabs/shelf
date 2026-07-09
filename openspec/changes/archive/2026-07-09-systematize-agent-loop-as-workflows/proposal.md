## Why

`docs/agent-loop.md` is the shelf's one standing instruction — read once per session by every
consumer agent, functionally a skill (trigger → decision procedure → output). It is currently
written as prose sections, not as addressable, deterministic procedures. Two concrete failures
traced to that shape this session: (1) only 2 of 7 resolutions (0006, 0007) were ever distilled
into it — 0001–0005 sit undistilled with nothing forcing the check; (2) real operational gaps
(worktree staleness on entry, fetch-cadence with no staleness bound, no upgrade-path artifact for
consumers) went unnoticed because there was no procedure enumerating what a workflow must cover.
Systematizing the loop into named, code-shaped workflows makes gaps visible by construction and
gives resolutions a required, checked landing spot.

## What Changes

- Restructure `docs/agent-loop.md` from numbered prose sections into named `WORKFLOW:` blocks
  (`TRIGGER:` / `STEPS:` / `OUTPUT:`), aggressively terse, pseudocode-shaped. Existing behavior
  carries over unchanged in substance: `SESSION-RESOLVE`, `SEAM` (four directions), `PROMOTE`,
  `RECEIVE`, `RECONCILE`, `ESCAPE-HATCH`.
- **New workflow `EVOLVE-THE-LOOP`**: the meta-procedure for updating the loop itself — friction
  found mid-session → trivial fix directly, or a resolution written AND distilled into the loop in
  the same change. Closes the "resolution never lands in the loop" gap directly.
- **BREAKING (process, not code):** every resolution must now carry a `Distilled into:` field
  (a workflow reference, or `N/A — self-enforcing via <test/tool>`). Enforced by a new blocking
  test mirroring `tests/test_catalog_projection.py`'s pattern. All 7 existing resolutions get this
  field backfilled.
- `PROMOTE` gains a worktree-freshness step (fetch + rebase on entering a shelf worktree) and a
  requirement that a breaking evolution write a `CHANGELOG.md` entry in the evolved package.
- `SESSION-RESOLVE`'s fetch-cadence rule gains a staleness bound (no longer purely
  once-per-session).
- New per-package `CHANGELOG.md` convention (terse, arrow-notation, AI-facing — not prose): one
  line per contract-shape change. `RECEIVE` references it as the first thing to read before
  diving into source or a README. `packages/anyllm/CHANGELOG.md` is written as the worked example,
  backfilled from the existing v0.1→v0.2 migration table.

## Capabilities

### New Capabilities
- `agent-loop-workflows`: the shelf's standing instruction file, expressed as named, addressable
  workflows (trigger/steps/output) rather than prose — covers session resolution, the four
  seam directions, promotion, receiving upgrades, reconciliation, the escape hatch, and evolving
  the loop itself.
- `resolution-distillation`: the requirement and mechanical check that every resolution states
  where (or whether) its decision lands in the operational loop.
- `package-changelog`: the terse, AI-facing changelog convention every shelf package's breaking
  evolution must produce.

### Modified Capabilities
(none — `openspec/specs/` has no existing capabilities; this change originates all three above.)

## Impact

- `docs/agent-loop.md` — full restructure (format change, not a behavior break for existing
  consumers; the four directions, PROMOTE procedure, etc. keep their current substance).
- `docs/resolutions/*.md` (all 7) — gain a `Distilled into:` frontmatter field.
- `docs/resolutions/README.md` — template gains the new mandatory field.
- `tests/` — new blocking test for the `Distilled into:` field (`make check` fails without it).
- `packages/anyllm/CHANGELOG.md` — new file, first entry backfilled.
- No package code changes. No consumer repo (a2kay, a2web) needs to act — the resolver block each
  consumer carries is unchanged; they pick up the restructured loop on their next lazy pull.
