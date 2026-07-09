## ADDED Requirements

### Requirement: Every resolution records where it lands operationally
Every file under `docs/resolutions/*.md` SHALL carry a `Distilled into:` frontmatter line naming
either the workflow it changed in `agent-loop.md`, or `N/A — self-enforcing via <test/tool>` when
the resolution does not change agent behavior at all.

#### Scenario: A resolution changes agent judgment
- **WHEN** a resolution's decision changes what an agent does at a seam (e.g. res 0007's
  monotonicity test)
- **THEN** its `Distilled into:` field names the `agent-loop.md` workflow it was folded into

#### Scenario: A resolution is purely structural/tooling
- **WHEN** a resolution's decision is enforced by a test, Makefile target, or repo layout rather
  than by an agent remembering a rule (e.g. res 0005, architecture rules as fitness tests)
- **THEN** its `Distilled into:` field reads `N/A — self-enforcing via <the specific test or tool>`

### Requirement: A missing distillation field fails the quality gate
`make check` SHALL fail if any file under `docs/resolutions/*.md` lacks a non-empty
`Distilled into:` line.

#### Scenario: A new resolution is authored without the field
- **WHEN** a resolution file is added or edited without a `Distilled into:` line
- **THEN** the corresponding test fails and `make check` reports the missing field, blocking the
  change from being considered done (no carve-outs, per `AGENTS.md` §1)

#### Scenario: All existing resolutions pass
- **WHEN** `make check` runs against the shelf as it stands after this change
- **THEN** all 7 existing resolutions (0001–0007) have a filled `Distilled into:` field and the
  test passes
