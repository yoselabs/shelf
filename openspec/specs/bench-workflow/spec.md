# bench-workflow Specification

## Purpose
TBD - created by archiving change docx-engine-verification. Update Purpose after archive.
## Requirements
### Requirement: The shelf has a named BENCH workflow for evidence-backed tool comparison
`docs/agent-loop.md` SHALL contain a `WORKFLOW: BENCH` capturing the reusable method for making an
engine/tool choice evidence-backed: frame the question as keep-vs-replace on a specific capability;
build a corpus by isolation (synthesize for semantic formats, select real documents for lossy ones,
never the user's own data); run each tool as a transient isolated install; grade model-free on named
axes; commit a dated findings doc; decide and record a ledger row. The workflow SHALL be extracted
from the PDF and docx benches (generalized from two instances), not invented ahead of them.

#### Scenario: An agent must choose between two libraries for a shelf package
- **WHEN** an agent faces a build-vs-adopt or keep-vs-replace decision between substrate tools
- **THEN** it finds `WORKFLOW: BENCH` in `agent-loop.md` and follows its steps rather than
  re-deriving a comparison method, producing a dated findings doc and a ledger row

#### Scenario: Corpus isolation technique is chosen by format
- **WHEN** an agent assembles a bench corpus
- **THEN** `WORKFLOW: BENCH` directs it to isolate by synthesis for semantic formats
  (docx/pptx/xlsx) and by selection of real documents for lossy formats (PDF, scans), and to never
  commit the user's own documents

### Requirement: An agent reasons about a package generically first, consumer second
`docs/agent-loop.md` SHALL state that an agent shaping a shelf package defines the capability set
generically (across the class of inputs at large) and uses the live consumer only to weight which
capabilities are common (light default) versus rare (opt-in / graceful degradation). A package's
capability grid SHALL NOT be scoped down to a single consumer's current diet.

#### Scenario: A package is shaped around one consumer's immediate need
- **WHEN** an agent is tempted to scope a shelf package's behavior to exactly what the one current
  consumer feeds it today
- **THEN** the loop directs it to define the generic capability set first and treat the consumer as
  weighting, so the package stays reusable substrate rather than a disguised single-consumer helper

