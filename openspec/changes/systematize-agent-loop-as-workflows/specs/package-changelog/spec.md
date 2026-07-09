## ADDED Requirements

### Requirement: Breaking package evolutions ship a terse, AI-facing CHANGELOG entry
Any shelf package whose evolution changes a contract shape (a call convention, a return type, a
failure mode) SHALL record a one-line-per-change, arrow-notation entry in
`packages/<name>/CHANGELOG.md`. Entries SHALL NOT contain prose rationale (that belongs in the
ledger) or a full migration essay (that belongs in the package README, optionally).

#### Scenario: A package evolves its contract
- **WHEN** `WORKFLOW: PROMOTE` ships a breaking evolution of an existing package
- **THEN** `packages/<name>/CHANGELOG.md` gains a new version heading with one arrow-notation line
  per contract-shape change (old shape ⇒ new shape), and no other content

#### Scenario: A release changes no contract shape
- **WHEN** a package release contains only internal refactors, bug fixes, or additions that don't
  change any existing call convention, return type, or failure mode
- **THEN** `CHANGELOG.md` gains no new entry for that release

### Requirement: Consumers reconciling a pin read CHANGELOG.md first
`WORKFLOW: RECEIVE` SHALL direct an agent to read the target package's `CHANGELOG.md` before
reading its README or source, when reconciling to a newer tag.

#### Scenario: An agent reconciles a2kay's anyllm pin from v0.1.0 to v0.2.0
- **WHEN** an agent begins `WORKFLOW: RECEIVE` for a package with a newer available tag
- **THEN** it reads `packages/anyllm/CHANGELOG.md` first to learn the exact shape changes required,
  before opening the package's source or README

### Requirement: anyllm's CHANGELOG.md exists as the worked example
`packages/anyllm/CHANGELOG.md` SHALL exist with at least one entry documenting the v0.1.0 → v0.2.0
evolution, in the arrow-notation format.

#### Scenario: The convention is verified against a real package
- **WHEN** `packages/anyllm/CHANGELOG.md` is read
- **THEN** it contains a `## 0.2.0` heading with arrow-notation lines matching the contract changes
  already documented in the anyllm README's migration table and `ledger/0032-anyllm-v2-delivered.toml`
