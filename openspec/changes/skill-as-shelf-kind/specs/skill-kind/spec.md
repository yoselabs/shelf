## Purpose

Defines what a shelf `MicroSoftware` with `kind = "skill"` must provide — the same five mechanism
slots every Kind answers (unit dir, contract-verify, pin/release, breaking-change signal, gate
membership), plus a token-budget assertion unique to skills.

## ADDED Requirements

### Requirement: The skill Kind governs only push-based, catalog-registered skills
`Kind: skill` and every requirement in this capability SHALL apply only to skills meant to
auto-trigger in a consumer's own, unrelated sessions via Claude Code's push-based discovery
(an installed plugin's `skills/` dir or `~/.claude/skills`). Shelf-process-internal tooling skills
under `.agents/skills/` (pull-based, invoked by path, e.g. `onboard-consumer`, `beads`) SHALL NOT be
required to carry a catalog entry, an eval suite, a tag, or a token-budget assertion under this
capability — that tier is out of scope, already works, and has no standing cost this contract exists
to bound.

#### Scenario: A shelf-internal tooling skill is added under `.agents/skills/`
- **WHEN** a new procedure is authored as `.agents/skills/<name>/SKILL.md`, invoked by an agent
  already working in or near the shelf's own repo
- **THEN** it is not a `Kind: skill` catalog member, carries no `claude plugin tag` release, and is
  not subject to this capability's token-budget or eval-coverage requirements

### Requirement: A skill member lives at `skills/<name>/`
A shelf `MicroSoftware` with `kind = "skill"` SHALL be identified by directory `skills/<name>/`,
parallel to a package's `packages/<name>/`, containing a `SKILL.md` whose frontmatter (`name`,
`description`) is the contract surface.

#### Scenario: An agent looks for a skill member's source
- **WHEN** an agent resolves the source of a catalog entry with `kind = "skill"`
- **THEN** it finds `skills/<name>/SKILL.md` at the shelf root, not `packages/<name>/`

### Requirement: A skill's contract is verified by `claude plugin eval`
A skill member's behavior SHALL be checked by `claude plugin eval` against cases under
`skills/<name>/evals/` (mirroring how a package's contract is checked by `pytest` under `make
check`). A skill member with no evals directory SHALL NOT be marked `active` in its catalog entry.

#### Scenario: A skill is promoted with no evals
- **WHEN** `WORKFLOW: PROMOTE` extracts a new skill and no `skills/<name>/evals/` directory exists
- **THEN** the skill's catalog status stays `candidate`, not `active`, until evals exist and pass

### Requirement: A skill's release is a validated git tag
A skill member's version SHALL be released via `claude plugin tag`, which SHALL refuse to create the
tag if `plugin.json`'s version and the shelf's `marketplace.json` entry for that skill disagree.

#### Scenario: A skill's plugin.json and marketplace.json versions drift
- **WHEN** an agent runs `claude plugin tag` for a skill whose `plugin.json` version does not match
  its `marketplace.json` entry's version
- **THEN** the tag is refused rather than created against a mismatched pair

### Requirement: A skill's breaking change is recorded like a package's
A skill whose `SKILL.md` frontmatter or trigger conditions change in a way that alters when it fires
or what it produces SHALL record a `CHANGELOG.md` entry in `skills/<name>/`, in the same
arrow-notation convention packages already use (capability `package-changelog`).

#### Scenario: A skill's trigger description changes materially
- **WHEN** a skill's `description` field is edited such that its firing conditions change (not a
  wording-only fix)
- **THEN** `skills/<name>/CHANGELOG.md` gains a new entry naming the old and new trigger condition

### Requirement: Every skill member is covered by the test gate
`make check` (or an equivalent skill-specific gate) SHALL fail if a directory exists under `skills/`
with no corresponding eval coverage, mirroring `test_gate_covers_every_package.py`'s guarantee for
packages — a skill gaining no verification is not silently invisible to the gate.

#### Scenario: A skill directory is added with no eval wiring
- **WHEN** a new `skills/<name>/` directory is committed with a `SKILL.md` but no eval case is wired
  into the gate
- **THEN** the gate fails, naming the uncovered skill directory

### Requirement: A skill member's always-on token cost is asserted
A skill's catalog entry SHALL record the always-on token cost reported by `claude plugin details
<name>` at the time of its last `PROMOTE` or `RECONCILE`, and `PROMOTE`/`RECONCILE` SHALL re-check
this figure against the skill's declared budget before marking it `active`.

#### Scenario: A skill's always-on cost is checked at promotion
- **WHEN** `WORKFLOW: PROMOTE` extracts a new skill
- **THEN** `claude plugin details <name>` is run, its always-on token figure is recorded in the
  skill's catalog entry, and the skill is not marked `active` if that figure exceeds its declared
  budget

#### Scenario: A skill's cost grows unnoticed across releases
- **WHEN** `WORKFLOW: RECONCILE` walks the catalog and reaches a skill entry
- **THEN** `claude plugin details <name>` is re-run and its current always-on figure is compared
  against the catalog's recorded figure, flagging drift for a design review rather than passing
  silently
