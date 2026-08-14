"""mcp-feedback — a drop-in, agent-invoked feedback tool for any FastMCP server.

Mounts a single `report_feedback(subject, note, request=None, response=None,
wanted=None)` tool with a FIXED schema — no consumer can rename, add, or
remove a field through any configuration this package exposes. `subject`
and `note` are required; `request`/`response`/`wanted` are optional free
text (v0.3.0 added `request`/`response` — what was actually asked/run and
what actually came back — after `note`/`wanted` alone proved to leave the
single most useful fact, what the caller actually got, with nowhere
first-class to go). Exactly two consumer-facing knobs exist:

- `endpoint`/`api_key` — transport config, resolved plain values. This
  package owns no environment variable names or settings schema of its own;
  a consumer resolves those however it already does (see `settings-base`
  for that half, if wanted).
- `extra_instructions` — appended to a fixed base tool description, never
  replacing it, for one line of consumer-specific guidance (e.g. "subject =
  the URL you fetched").

Reports are deliberately self-contained — no correlation ID, session ID, or
any other automatic link to the call that prompted the report. Nothing else
is threaded in; the calling agent decides how much of `request`/`response`/
`wanted` is worth including, not a rigid schema this package would
otherwise have to keep inventing fields for. (v0.1.0 attached FastMCP's
`ctx.session_id`; reversed in v0.2.0 — it also made the tool's underlying
function require a live MCP request/session to run at all, breaking any
consumer that invokes tool functions directly outside of one, e.g. a CLI.)

Delivery is OTLP/HTTP-logs over a hand-rolled async `httpx` POST — not the
OTel Logs SDK (`opentelemetry.sdk._logs` is unstable/private in the Python
SDK, and its exporter is synchronous). Best-effort and non-blocking: a
delivery failure is logged, never raised, and `sent` on the result reflects
whether a send was attempted, never whether it was confirmed delivered.
"""

from __future__ import annotations

from mcp_feedback._tool import FeedbackReportResult, register_feedback_tool

__all__ = ["FeedbackReportResult", "register_feedback_tool"]
