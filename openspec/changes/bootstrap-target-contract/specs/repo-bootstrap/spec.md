## ADDED Requirements

### Requirement: A repo is onboarded by one command, not by following a document

A repo SHALL provide a `make bootstrap` target that brings a fresh clone to a fully configured,
verified state. Onboarding documentation SHALL point at that target rather than enumerate manual
steps for a reader to perform.

#### Scenario: An agent or person meets an unfamiliar clone

- **WHEN** they need to make the clone ready for work
- **THEN** `AGENTS.md` and `docs/consuming-the-shelf.md` direct them to `make bootstrap`, and no
  correct onboarding requires reading a runbook first

#### Scenario: A repo has no Makefile

- **WHEN** a consumer repo cannot provide the target
- **THEN** the manual path remains documented, and the contract states which obligations that
  consumer is now carrying by hand

### Requirement: Bootstrap is idempotent

`make bootstrap` SHALL be safe to run any number of times. A second run against an
already-bootstrapped repo SHALL make no further change.

#### Scenario: Bootstrap runs twice

- **WHEN** `make bootstrap` completes and is immediately run again
- **THEN** the repo's git config, hook files, and tool configuration are identical after the
  second run, and the second run reports success

#### Scenario: Bootstrap runs against a partially configured repo

- **WHEN** some steps were already applied and others were not
- **THEN** the missing steps are applied and the applied ones are left alone — bootstrap
  converges rather than requiring a clean starting state

### Requirement: Ordering constraints are encoded as prerequisites

Where one bootstrap step must precede another, that ordering SHALL be expressed as a target
prerequisite. It SHALL NOT be conveyed only as documentation.

#### Scenario: A repo uses both the pre-commit framework and beads

- **WHEN** `make bootstrap` runs on a repo configured for both
- **THEN** the pre-commit hook is installed before beads is initialized, so beads chains into
  the existing native hook instead of seizing `core.hooksPath` — and this holds regardless of
  what any reader knew about the ordering

#### Scenario: Someone reorders the targets

- **WHEN** a maintainer reads the bootstrap target intending to change step order
- **THEN** the finding that motivated each non-obvious ordering is stated at that prerequisite

### Requirement: Verification asserts effects, never artifacts

`make bootstrap-verify` SHALL confirm each installed thing by exercising it and observing the
result. It SHALL NOT accept the existence of a file, the presence of a marker, or a permission
bit as evidence that a step succeeded.

#### Scenario: A hook exists but git will never run it

- **WHEN** a pre-commit hook is present and executable in a directory git does not read
  (because `core.hooksPath` points elsewhere)
- **THEN** verification fails, and reports both the directory written to and the directory git
  actually reads

#### Scenario: Configuration was set and later reverted

- **WHEN** a tool's configuration was applied, then reverted by a git operation that restored
  tracked files
- **THEN** verification reads the value back through the tool and fails, rather than trusting
  that the original write succeeded

#### Scenario: Two tools contend for the hook slot

- **WHEN** the repo has a pre-commit framework configuration and `core.hooksPath` set to
  another tool's directory
- **THEN** verification reports the contention, names which tool currently owns the slot, and
  does not silently pick one

### Requirement: Verification distinguishes three outcomes

Verification SHALL report *verified*, *failed*, and *could not be verified* as distinct
outcomes, each with its own exit status and message. An inability to check SHALL NOT be
reported as a pass.

#### Scenario: A check cannot run in the current environment

- **WHEN** an assertion's preconditions are absent — a dependency is not installed, or the
  environment cannot execute hooks
- **THEN** the outcome is reported as could-not-verify, distinctly from success, so that an
  unchecked property is never mistaken for a checked one

### Requirement: Content assertions live in the gate; environment assertions do not

Assertions about the repository's own content SHALL run as part of `make check`, so that they
hold on any clone regardless of whether it was bootstrapped. Assertions about a working copy's
configuration SHALL live in `make bootstrap-verify` and SHALL NOT gate `make check`.

#### Scenario: An unbootstrapped clone violates a content rule

- **WHEN** a clone that never ran `make bootstrap` — with no hooks installed and no tooling
  configured — introduces a local `path=`/editable shelf source
- **THEN** `make check` fails on it, because the assertion reads the repo's files and depends
  on nothing that onboarding installs

#### Scenario: A hook is dead but the content is correct

- **WHEN** the pre-commit hook has been disabled or is unreachable, and the repo's content
  violates no rule
- **THEN** `make check` passes, and the broken hook is reported by `make bootstrap-verify` as a
  degraded-feedback problem rather than a gate failure

#### Scenario: Verification is asked to run where hooks are meaningless

- **WHEN** the environment never commits — continuous integration, or a container running only
  the gate
- **THEN** no hook or issue-tracker state is required, and no CI-specific mode, skip flag, or
  special case is needed to make the gate pass

#### Scenario: Verification encounters a repairable problem

- **WHEN** `make bootstrap-verify` finds environment state it could fix
- **THEN** it reports and exits non-zero without changing anything, directing the operator to
  `make bootstrap` — a check that silently repairs is a check that hides drift
