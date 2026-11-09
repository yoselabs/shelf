# Semantic Codex launch

## MODIFIED Requirements

### Requirement: Owning fresh and resume construction
CodexHarness.launch_spec MUST build fresh/resume argv from semantic LaunchInputs;
LaunchInputs MUST NOT expose raw cli replacement or an empty-cli compatibility path.
Model/effort/sandbox/access/isolation/schema/output/process context MUST be honored
using each operation's supported syntax. Explicit resume MUST name its session.

#### Scenario: Fresh plan attempt
- WHEN a nonsealed caller supplies semantic choices without vendor argv
- THEN the final spec includes exec and all supplied semantic choices, schema/output
- AND prompt/environment/cwd are preserved without a shell or model call.

#### Scenario: Empty choices
- WHEN optional choices are empty
- THEN their flags are omitted without inventing policy defaults
- AND empty nonsealed executable/cwd or explicit resume is refused.

#### Scenario: Existing sealed consumer
- WHEN a caller requests sealed completion
- THEN existing sealed policy and its own skip-Git behavior remain unchanged.
