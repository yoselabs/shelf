## ADDED Requirements

### Requirement: Onboarding order is enforced by preconditions, not by instructions

Each onboarding operation SHALL declare its preconditions and SHALL refuse to run when they are
not met and verified. Ordering SHALL NOT be conveyed only in the skill's text, documentation, or
any other prose a caller is trusted to follow.

#### Scenario: Beads is attempted before the commit guard

- **WHEN** the `beads` operation is invoked on a repo where the `guard` operation has not
  completed and verified
- **THEN** it refuses and reports the unmet precondition, so `bd init` cannot seize
  `core.hooksPath` and leave the guard installed dead

#### Scenario: A precondition's artifact exists but its effect was never confirmed

- **WHEN** a dependent operation's precondition is satisfied only by an artifact — a hook file
  present, a marker found, a permission bit set — with no verified effect
- **THEN** the precondition is treated as unmet, because an artifact is not evidence that a step
  worked

#### Scenario: Operations are invoked by something other than the skill

- **WHEN** a person, a `make` target, or a different agent invokes the operations directly and
  in the wrong order
- **THEN** the same refusal occurs — correctness does not depend on the skill being read,
  current, or followed

### Requirement: Every operation is idempotent, effect-asserting, and honest about failure

Each operation SHALL be safe to re-run, SHALL confirm its result by exercising it rather than by
inspecting what it wrote, and SHALL report *applied*, *failed*, and *could not apply* as distinct
outcomes.

#### Scenario: Onboarding runs against an already-onboarded repo

- **WHEN** onboarding is re-run on a repo that is fully onboarded
- **THEN** every operation reports no-op, changes nothing, and the run succeeds — so re-running
  it to check a repo's state is safe

#### Scenario: An operation cannot apply in this repo

- **WHEN** an operation's target is absent — the Python preset in a repo with no `pyproject.toml`
- **THEN** it reports could-not-apply, distinctly from both success and failure, and the run
  continues with the operations that do apply

#### Scenario: An operation would overwrite something it does not own

- **WHEN** applying would clobber a file or region managed by another tool
- **THEN** the operation refuses, names what owns it, and changes nothing

### Requirement: Onboarding adapts to the repository it finds

Onboarding SHALL inspect the target repository and select operations accordingly. It SHALL NOT
assume a greenfield repo, a particular hook manager, or that beads is wanted.

#### Scenario: The repo already uses another hook manager

- **WHEN** the target already has hooks managed by the pre-commit framework, husky, or lefthook
- **THEN** onboarding detects which tool owns the hook path, reports it, and proceeds only in a
  way that leaves that tool working

#### Scenario: The target is not a Python project

- **WHEN** the repo has no Python toolchain to inherit the preset
- **THEN** the stack-agnostic operations still complete, and onboarding states plainly which
  parts were not applied rather than partially applying a Python preset

#### Scenario: Beads is not wanted

- **WHEN** the operator declines beads
- **THEN** onboarding completes without it, and every other operation still applies — beads is
  opt-out, not a prerequisite

### Requirement: Onboarding never adds a shelf dependency

Onboarding SHALL NOT add entries to `[tool.uv.sources]` or otherwise introduce a dependency on a
shelf package.

#### Scenario: A newly onboarded project has no shelf dependency yet

- **WHEN** onboarding completes on a new project
- **THEN** no shelf package has been added, because a dependency is adopted when a real need
  passes the DEEP · STABLE · WINS gate — never as a side effect of onboarding

### Requirement: The resolver block is projected, not pasted

The shelf resolver block SHALL be written into the consumer's agent instructions as a
marker-delimited region that can be re-projected and checked for drift.

#### Scenario: The upstream resolver block changes

- **WHEN** the canonical block in shelf changes and onboarding is re-run on a consumer
- **THEN** the consumer's region is updated in place, and drift is detectable rather than silent

#### Scenario: The consumer's agent file already carries other managed regions

- **WHEN** the target `AGENTS.md` already contains managed blocks belonging to other tools
- **THEN** the resolver block is written outside every one of them, and no other tool's region is
  modified

#### Scenario: The consumer's CLAUDE.md is a symlink

- **WHEN** `CLAUDE.md` is a symlink to `AGENTS.md`
- **THEN** the block is written once, to the link's target, and the symlink is preserved
