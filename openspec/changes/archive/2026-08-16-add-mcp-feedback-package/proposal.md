## Why

Two consumer apps (a2web now, more to follow) need agents to be able to
report their own subjective feedback on a tool call — mechanical checks
structurally cannot catch "the result was fine but not what I needed."
a2web already built and shipped this once, scoped entirely to its own
fetch domain (`url` param, fetch-specific correlation). That version can't
be reused as-is: reuse across an unrelated MCP project (a calendar server,
a database server, ...) requires the tool's subject, fields, and output
shape to carry zero fetch-specific assumptions. Building it once, generic,
on the shelf — rather than re-deriving the same free-text-fields-not-a-
taxonomy decision per consumer — is a DEEP · STABLE · WINS case: the shape
(two free-text fields, no closed category, OTLP/HTTP-logs transport) is
already validated against one real consumer's drift data (a2web's own
`severity` attribute arrived in 5 different casings once real callers
touched it), and every future FastMCP-based consumer needs the identical
mechanism, differing only in where it posts and what extra copy it wants
in the tool description.

## What Changes

- New package `mcp-feedback`: a single `register_feedback_tool(mcp, *,
  endpoint, api_key, extra_instructions=None)` entry point that mounts a
  fixed `report_feedback(subject, note, wanted=None) ->
  FeedbackReportResult{sent: bool}` tool on a FastMCP server.
- Fixed, non-configurable schema across every consumer: tool name,
  parameter names/types, output shape, no closed category/taxonomy.
- Auto-attaches `ctx.session_id` (FastMCP's own per-client-session
  identifier) as the only correlation signal — named explicitly as a
  stopgap pending MCP's own discussed native call-linking/feedback
  mechanism, not a permanent design.
- Hand-rolled async OTLP/HTTP-logs POST transport (not the OTel Logs SDK —
  unstable/private Python API, sync-only exporter).
- Exactly two consumer-supplied customization points: `endpoint`/`api_key`
  (plain resolved config values — the package owns no env var names or
  settings schema, same split as `settings-base`) and `extra_instructions`
  (appended to a fixed base docstring, never replacing it).
- The second FastMCP-coupled shelf package, after `mcp-result-wire`.

## Capabilities

### New Capabilities
- `mcp-feedback-tool`: a FastMCP-mountable, agent-invoked feedback-reporting
  tool with a fixed schema and exactly two consumer-configurable knobs
  (transport config, docstring addendum), delivering reports over
  OTLP/HTTP-logs.

### Modified Capabilities
(none — new package, no existing shelf spec's requirements change)

## Impact

- New directory `packages/mcp-feedback/` (src, tests, pyproject.toml,
  README.md) following the `mcp-result-wire`/`settings-base` layout.
- New `catalog/mcp-feedback.toml` entry, `status = "candidate"` (born
  candidate — protection is earned once a 2nd real consumer pulls it, per
  `docs/doctrine.md`).
- Adds `fastmcp` and `httpx` as this package's own dependencies (fastmcp
  already a dependency of `mcp-result-wire`, so not a new shelf-wide
  dependency).
- Does not touch any existing shelf package.
- a2web's own adoption (deleting its local `report_feedback` and mounting
  this package instead) is tracked as a separate a2web-side change, not
  part of this proposal — this proposal only creates the shelf package.
