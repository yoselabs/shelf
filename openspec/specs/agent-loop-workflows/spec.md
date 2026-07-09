# Capability: agent-loop-workflows

## Purpose
The shelf's standing instruction file, expressed as named, addressable workflows (trigger/steps/output) rather than prose — covers session resolution, the four seam directions, promotion, receiving upgrades, reconciliation, the escape hatch, and evolving the loop itself.

## Requirements

### Requirement: Loop content is expressed as named workflows
`docs/agent-loop.md` SHALL express every behavioral rule as a named `WORKFLOW:` block with an
explicit `TRIGGER:`, numbered `STEPS:`, and an `OUTPUT:`. No behavioral rule SHALL be stated only
as free prose outside a workflow block.

#### Scenario: An agent looks up what to do at a seam
- **WHEN** an agent is about to write a helper, wrapper, or adapter (a substrate seam)
- **THEN** it finds a `WORKFLOW: SEAM` block in `agent-loop.md` whose `TRIGGER:` matches its
  situation, with numbered steps to follow (ADOPT / EVOLVE / PROMOTE / DUPLICATE)

#### Scenario: Every pre-existing rule is preserved
- **WHEN** `agent-loop.md` is reformatted from its prior prose sections into workflow blocks
- **THEN** every rule present in the prior version maps to at least one step in a workflow —
  none are silently dropped in the reformatting

### Requirement: The loop defines a procedure for evolving itself
`docs/agent-loop.md` SHALL contain a `WORKFLOW: EVOLVE-THE-LOOP` whose trigger is friction with the
loop discovered mid-session, and whose steps require that any non-trivial fix be backed by a
resolution distilled into the loop in the same change.

#### Scenario: An agent hits a gap in the loop
- **WHEN** an agent mid-session finds a judgment call the loop does not cover
- **THEN** it follows `WORKFLOW: EVOLVE-THE-LOOP`: fix directly if trivial, otherwise write a
  resolution and distill the operational takeaway into the relevant workflow block in the same
  change — never merging the resolution without the distillation

### Requirement: Worktree freshness is checked on PROMOTE entry
`WORKFLOW: PROMOTE`'s first step SHALL be fetching and rebasing the shelf worktree onto
`origin/main` before any file is edited.

#### Scenario: A shelf worktree is reused in a new session
- **WHEN** an agent begins `WORKFLOW: PROMOTE` in an existing `../shelf-<project>` worktree
- **THEN** it first runs `git fetch && git rebase origin/main` (or `pull --ff-only` if the branch
  has no local commits) before touching any file

### Requirement: Fetch cadence has a staleness bound
`WORKFLOW: SESSION-RESOLVE`'s fetch-cadence rule SHALL bound how long a cached pull may be relied
upon within a single session, not rely purely on "once per session."

#### Scenario: A session runs long enough for the cached pull to go stale
- **WHEN** an agent's cached shelf pull is older than the stated staleness bound and it is about
  to enter `WORKFLOW: SEAM` or `WORKFLOW: PROMOTE`
- **THEN** it re-pulls before proceeding, rather than acting on the stale cache
