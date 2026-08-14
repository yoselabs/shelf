## Context

See `proposal.md` for motivation. This design carries forward reasoning
already settled once in a2web's own archived changes rather than
re-litigating it — cited inline where it applies, not re-derived.

- a2web's archived `add-agent-invoked-feedback-tool` design (D1-D6, at
  `a2web/openspec/changes/archive/2026-08-12-add-agent-invoked-feedback-tool/design.md`)
  already validated: two free-text fields over a closed taxonomy, a
  hand-rolled OTLP transport over the OTel Logs SDK, `sent: bool` as
  attempt-not-delivery, best-effort/never-raise semantics. This package
  reuses those conclusions rather than re-deciding them.
- a2web's archived `unify-otel-telemetry-seam` design D1 independently
  rejected the OTel Logs SDK for the same reason (`opentelemetry.sdk._logs`
  is unstable/private in the Python SDK; its exporter is sync-only). Two
  independent evaluations landed on the same answer.
- `mcp-result-wire` is the shelf's only existing FastMCP-coupled package
  (`catalog/mcp-result-wire.toml`) — precedent that a shelf package may
  depend on `fastmcp` without breaking the shelf's substrate-indifference
  norm, as long as the coupling is to the protocol layer (FastMCP's
  `Context`/tool registration), not to a specific consumer app.
- `settings-base`'s catalog note is the precedent for the config split
  here: "the generic loader machinery only... the AppSettings schema...
  stay[s] in [the consumer]." This package takes resolved `endpoint`/
  `api_key` strings, not env var names — it has no opinion on how a
  consumer resolves them.
- Verified against the actually-installed `fastmcp` (3.4.4, via a2web's
  environment) this session: `Context.session_id` spans a whole client
  session across multiple tool calls; `Context.request_id` is per-call
  only; there is no FastMCP or MCP-protocol mechanism today for a later
  tool call to reference a specific earlier one. `session_id` is therefore
  the best available correlation signal, not a complete one.

## Goals / Non-Goals

**Goals:**
- One mechanism, mounted identically by any FastMCP server, with a schema
  that cannot drift between consumers.
- Minimize the consumer-facing surface to exactly what genuinely differs
  per deployment (where reports go, one line of tool-description copy).
- Reuse, not re-derive, the free-text/no-taxonomy and transport decisions
  a2web already validated against real drift data.

**Non-Goals:**
- Not solving call-level correlation (linking a report to the one specific
  prior tool call it concerns). No mechanism exists in MCP today to do
  this reliably; `session_id` is the accepted stopgap, named as such.
- Not attempting self-judgment reliability mitigation (a bare feedback
  report is one model's unverified opinion) — same open risk a2web's
  archived design named and deferred; not this package's problem to solve.
- Not providing the mechanical/pipeline-triggered feedback pattern (a
  fetch pipeline auto-reporting on its own hint/confidence signals) — that
  stays consumer-local by design (see proposal's Impact section); this
  package covers only the agent-invoked case.
- Not building a generic "any MCP tool" wrapper beyond the feedback use
  case — no attempt to generalize into a broader telemetry framework here.

## Decisions

### D1 — Package name and shape: `mcp-feedback`, `kind = "any-*"`

Checked `packages/` and `catalog/` for collisions: none. Named for what it
mounts (an MCP-facing feedback tool), not for its transport (OTLP is an
implementation detail, not the identity). `kind = "any-*"` matches
`mcp-result-wire`'s own classification — a shelf package coupled to the
MCP/FastMCP protocol layer, not to a specific consumer domain. Tier: T2
(depends on `fastmcp` + `httpx`, not a T0/T1 leaf primitive).

### D2 — `subject`, not `url`: no domain assumption in the schema

**Alternative rejected:** keep a2web's original `url: str` parameter name,
since URLs cover the majority case (fetch tools, most read-oriented MCP
servers). Rejected because "majority case" is exactly the trap — a
database-MCP's feedback subject is a table or query, a calendar-MCP's is
an event id, and forcing either to write a URL-shaped string into a field
literally named `url` is a worse ergonomic hazard than an honestly generic
name. `subject: str`, free text, no shape assumed.

### D3 — No closed category (carried forward from a2web's D2)

Direct evidence: a2web's own mechanical `severity` attribute — a simpler,
narrower value than any feedback taxonomy would be — arrived in five
different casings once real callers touched it
(`unify-otel-telemetry-seam` design D5/D7, `feedback-telemetry`
capability). A `category` enum on this tool would face the same drift, with
a worse failure mode: an agent under token/time pressure picks the closest
available bucket rather than the correct one, silently lossy. `note`/
`wanted` stay free text; taxonomy-mining, if ever wanted, happens later
over collected free text with more context to calibrate consistently.

### D4 — Exactly two configuration knobs, enforced by the function signature

`register_feedback_tool(mcp: FastMCP, *, endpoint: str, api_key: str,
extra_instructions: str | None = None) -> None`. The signature itself is
the enforcement mechanism — there is no third parameter to add without a
new spec requirement to justify it (per this change's ADDED requirement
"Exactly two consumer-configurable knobs"). `extra_instructions` is
concatenated onto a fixed base docstring string owned by this package;
consumers never see or can override the base text itself.

**Alternative rejected:** let consumers pass a full replacement docstring.
Rejected because the base explanation ("no category to pick, just say
what's wrong, subject is your own words for what this concerns") is
exactly the part that must stay identical across consumers for this
package's own core promise ("schema should be the same, easily pluggable")
to hold — a replaceable base invites the same drift D3 rejects for fields,
just moved into free-text docs instead of a taxonomy field.

### D5 — Correlation: none — reports are self-contained (REVERSED in v0.2.0)

**Original v0.1.0 decision (superseded):** attach `ctx.session_id`
(FastMCP session-scoped) to every report as the only correlation signal
beyond timestamp proximity — no `report_id`/`trace_id` minted, no attempt
to look up or reference a prior tool call.

**Reversed after the first real adoption attempt found a structural
problem, not a taste objection:** a2web's own CLI derives each terminal
command by calling a tool's underlying Python function directly
(`inspect.signature(fn)` + `fn(**kwargs)`), bypassing FastMCP's
request/session machinery entirely — that's how a CLI command runs without
a live MCP client. `Context.session_id` raises `RuntimeError` outside a
real request/session, so requiring `ctx: Context` in the tool's signature
made the function itself unusable from any caller that doesn't go through
a full MCP session — not an a2web quirk, a structural conflict with "a
FastMCP tool's underlying function should be plainly callable," which this
package's own README now states as an explicit goal.

**Current decision:** no correlation mechanism at all. The tool's own
description instead asks the calling agent to make the report
self-contained — state what it was trying to do, what it expected, what it
actually ran and with what parameters, what it got instead, and any
nice-to-have, at the agent's own judgment. This trades "reports are
automatically linkable to a session" for "the tool's function has zero
runtime dependency beyond its own arguments" — judged the better trade
once a real consumer's CLI hit the alternative's cost directly, not
speculatively.

### D6 — Transport: hand-rolled OTLP/HTTP-logs POST, own module

A self-contained async `httpx` POST to `endpoint` with `X-Api-Key:
api_key`, 5s timeout, OTLP/HTTP logs JSON shape
(`resourceLogs[].scopeLogs[].logRecords[]`), swallowing `httpx.HTTPError`/
`OSError` into a warning log rather than raising. This is the same
transport shape a2web's archived designs already validated twice
independently (D1 in both `add-agent-invoked-feedback-tool` and
`unify-otel-telemetry-seam`) — not re-decided here, just re-implemented
generic. `scope.name` is fixed to `mcp.feedback.agent` so downstream
gateways can distinguish this package's reports from anything else on the
same stream without per-consumer configuration.

## Risks / Trade-offs

- **[Accepted, named] Session-only correlation is weak.** See D5. Not
  mitigated here; the real fix is a protocol-level mechanism this package
  doesn't control.
- **[Accepted, named] Self-judgment reliability.** A bare `report_feedback`
  call is one model's unverified opinion. Same risk a2web's archived
  design already named and deferred — not re-solved here, and not this
  package's concern to solve since it's orthogonal to the transport/schema
  question.
- **[Trade-off] No per-consumer field customization at all** — a consumer
  with a genuinely different need (e.g. wanting a fourth field) cannot get
  it from this package without a shelf-side change. Accepted deliberately:
  the whole value proposition is one identical shape everywhere: a
  consumer that needs more should question whether it's still "feedback"
  in this package's sense, not fork the schema.
- **[Risk] Free-text `subject`/`note`/`wanted` carry the same
  prompt-injection-surface caution already named in a2web's archived
  `unify-otel-telemetry-seam` design D5** — anything downstream that feeds
  stored reports back into an LLM must treat them as data, not
  instructions. Same caution, not new.

## Migration Plan

This proposal creates the shelf package only. a2web's own migration
(delete its local `report_feedback`/`feedback_transport.py`, adopt this
package, drop `url` in favor of `subject`, update its wire contract
goldens for the schema change) is a separate a2web-side change, tracked
after this package reaches a usable `status`. No rollback concerns at the
shelf level — this is a net-new package, nothing existing depends on it
yet.

## Open Questions

None — the two customization-knob boundary and the correlation stopgap
were both resolved explicitly with the requester this session, not left
ambiguous.
