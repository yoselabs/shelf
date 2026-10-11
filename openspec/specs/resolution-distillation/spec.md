# Capability: ADR-distillation

## Purpose
The requirement and mechanical check that every ADR states where (or whether) its decision lands in the operational loop.

## Requirements

### Requirement: Every ADR records where it lands operationally
Every file under `docs/adr/*.md` SHALL carry a `distilled_into:` frontmatter field naming
either the workflow it changed in `agent-loop.md`, or `N/A — self-enforcing via <test/tool>` when
the ADR does not change agent behavior at all.

#### Scenario: An ADR changes agent judgment
- **WHEN** an ADR's decision changes what an agent does at a seam (e.g. ADR 0007's
  monotonicity test)
- **THEN** its `distilled_into:` field names the `agent-loop.md` workflow it was folded into

#### Scenario: An ADR is purely structural/tooling
- **WHEN** an ADR's decision is enforced by a test, Makefile target, or repo layout rather
  than by an agent remembering a rule (e.g. ADR 0005, architecture rules as fitness tests)
- **THEN** its `distilled_into:` field reads `N/A — self-enforcing via <the specific test or tool>`

### Requirement: A missing distillation field fails the quality gate
`make check` SHALL fail if any file under `docs/adr/*.md` lacks a non-empty
`distilled_into:` frontmatter field.

#### Scenario: A new ADR is authored without the field
- **WHEN** an ADR file is added or edited without a `distilled_into:` line
- **THEN** the corresponding test fails and `make check` reports the missing field, blocking the
  change from being considered done (no carve-outs, per `AGENTS.md` §1)

#### Scenario: All existing ADRs pass
- **WHEN** `make check` runs against the shelf as it stands after this change
- **THEN** all existing ADRs have a filled `distilled_into:` field and the
  test passes
