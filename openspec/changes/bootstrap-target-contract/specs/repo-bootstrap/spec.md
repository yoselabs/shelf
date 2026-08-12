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

### Requirement: The standing gate verifies bootstrap state and never repairs it

`make check` SHALL depend on verification of bootstrap state, so that decay fails the build.
That verification SHALL be read-only.

#### Scenario: Bootstrap state decays after onboarding

- **WHEN** configuration is reverted, a hook is disabled, or a clone was never bootstrapped
- **THEN** the next `make check` fails and names what is not live — the drift announces itself
  rather than waiting to be noticed

#### Scenario: The gate encounters a repairable problem

- **WHEN** verification finds state it could fix
- **THEN** it reports and fails without changing anything, directing the operator to
  `make bootstrap` — a gate that silently repairs is a gate that hides drift
