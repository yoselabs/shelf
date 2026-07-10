# Capability: docx-engine-comparison

## ADDED Requirements

### Requirement: The docx bench isolates one capability per fixture
The docx corpus SHALL consist of fixtures that each exercise exactly one docx capability (tracked
changes, OMML equation, embedded image, footnote, nested table, nested list, headings/styles, clean
baseline), so a scoring difference attributes to a single feature. Semantic-format fixtures SHALL be
synthesized (authored to carry one feature and nothing else); only synthesis-weak capabilities (OMML
math, embedded images) MAY use real public documents.

#### Scenario: An engine mishandles tracked changes
- **WHEN** the bench scores a fixture that contains exactly one tracked insertion and no other
  non-baseline feature
- **THEN** any grade difference between engines on that fixture is attributable to tracked-changes
  handling alone, not confounded with tables/math/images

#### Scenario: The user's own documents are never committed
- **WHEN** the capability grid is assembled
- **THEN** no user-supplied document is committed to `bench/corpus/`; the user's real docx inform
  only the capability weighting and local grade sanity-checks

### Requirement: Engines are compared as transient isolated installs
Each docx engine SHALL run via a transient isolated install (`uv run --with <engine>`), never added
as a declared dependency of `convert-md` merely to be benched. pandoc SHALL be scored in both
`--track-changes=accept` and `--track-changes=all` modes to quantify the redline behavior rather
than assume it.

#### Scenario: Reproducing the comparison later
- **WHEN** an agent re-runs the docx bench against a newer engine release
- **THEN** it uses the same isolated-install harness and model-free rubric, and the dated findings
  doc under `bench/results/` records the comparison as a committed artifact

### Requirement: The docx engine decision is recorded with evidence
The engine decision (single engine, or a tiered light-default + opt-in-pandoc + graceful
degradation) SHALL be recorded in a design decision and a `ledger/*.toml` row, and the
`convert-md` version re-cut accordingly. If pandoc is dropped from the mandatory `documents` extra,
`pypandoc-binary` SHALL be removed from that extra.

#### Scenario: A consumer needs redline preservation after pandoc is de-defaulted
- **WHEN** the decision is a tiered path and a consumer installs `convert-md` without the pandoc tier
- **THEN** docx conversion still succeeds on clean content and degrades gracefully on tracked changes
  (`lost=["tracked_changes"]` in the result), never raising an ImportError
