## Purpose

Gives any FastMCP-based server a drop-in, agent-invoked tool for reporting
subjective feedback on a tool call's result — the class of failure no
mechanical check can catch — with a fixed, non-negotiable schema across
every consumer and exactly two consumer-configurable knobs: transport
config and an optional docstring addendum.

## ADDED Requirements

### Requirement: Fixed tool schema across every consumer
`register_feedback_tool` SHALL mount a tool named `report_feedback` with
exactly three parameters — `subject: str` (required, what the feedback
concerns, in the caller's own words), `note: str` (required, what was
wrong), `wanted: str | None` (optional, what the caller would have
preferred) — and no other parameters. No consumer of this package SHALL be
able to rename, add, remove, or type-change these parameters through any
configuration this package exposes.

#### Scenario: Two independent consumers mount an identical schema
- **WHEN** two unrelated FastMCP servers each call `register_feedback_tool`
  with different `endpoint`/`api_key` values
- **THEN** both servers expose a `report_feedback` tool with byte-identical
  parameter names, types, and requiredness

### Requirement: No closed feedback category
The tool SHALL NOT expose any enum, closed vocabulary, or severity field
for the caller to self-classify its feedback into. `note` and `wanted`
SHALL be free text only.

#### Scenario: Caller cannot self-categorize
- **WHEN** inspecting the tool's input schema
- **THEN** no parameter has a fixed set of allowed values

### Requirement: Exactly two consumer-configurable knobs
`register_feedback_tool` SHALL accept only `endpoint: str`, `api_key: str`
(transport configuration, resolved plain values — this package SHALL own
no environment variable names or settings schema of its own) and
`extra_instructions: str | None` (appended to a fixed base tool docstring,
never replacing it). No other consumer-facing configuration surface SHALL
exist.

#### Scenario: extra_instructions appends, does not replace
- **WHEN** a consumer passes `extra_instructions="subject = the URL you
  fetched"`
- **THEN** the mounted tool's docstring contains both the package's fixed
  base explanation and the consumer's appended text

#### Scenario: extra_instructions omitted
- **WHEN** a consumer omits `extra_instructions`
- **THEN** the mounted tool's docstring contains only the package's fixed
  base explanation

### Requirement: No correlation — reports are self-contained
The tool SHALL NOT attach any correlation identifier (session ID, request
ID, or otherwise) to a report, and SHALL NOT attempt to correlate a report
to any specific prior tool call — no call-linking mechanism SHALL be
invented by this package. The tool's description SHALL instead direct the
calling agent to make each report self-contained.

#### Scenario: No correlation identifier is attached
- **WHEN** an agent calls `report_feedback`
- **THEN** the outgoing report contains no field beyond `subject`, `note`,
  and (when supplied) `wanted`

### Requirement: The tool's underlying function requires no live MCP session
`report_feedback`'s underlying function SHALL be directly callable with
only `subject`/`note`/`wanted` as arguments, without an active MCP
request or session — so a consumer that invokes tool functions directly
(e.g. a CLI that derives commands from tool signatures rather than
running a full MCP client) can call it.

#### Scenario: Direct call with no session succeeds
- **WHEN** the tool's underlying function is called directly, with no
  FastMCP request or session active
- **THEN** it returns normally instead of raising

### Requirement: Best-effort, non-blocking delivery
The tool SHALL report `sent: bool` reflecting whether delivery was
attempted (both `endpoint` and `api_key` configured), never whether it was
confirmed delivered. A transport failure SHALL be swallowed (logged, not
raised) and SHALL NOT surface as a tool-call error to the caller.

#### Scenario: Endpoint unreachable
- **WHEN** the configured `endpoint` refuses the connection
- **THEN** `report_feedback` still returns normally with `sent: true`, and
  no exception propagates to the calling agent

#### Scenario: Not configured
- **WHEN** `endpoint` or `api_key` is empty
- **THEN** `report_feedback` returns `sent: false` and performs no network
  call

### Requirement: OTLP/HTTP-logs transport, not the OTel Logs SDK
Reports SHALL be sent as OTLP/HTTP logs payloads over a hand-rolled async
HTTP POST. This package SHALL NOT depend on `opentelemetry-sdk`'s Logs API.

#### Scenario: No OTel SDK dependency
- **WHEN** inspecting this package's dependencies
- **THEN** `opentelemetry-sdk` (or any `opentelemetry-*` package) is absent
