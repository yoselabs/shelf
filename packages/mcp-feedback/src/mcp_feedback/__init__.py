"""mcp-feedback — a drop-in, agent-invoked feedback tool for any FastMCP server.

Mounts a single `report_feedback(subject, note, wanted=None)` tool with a
FIXED schema — no consumer can rename, add, or remove a field through any
configuration this package exposes. Exactly two consumer-facing knobs exist:

- `endpoint`/`api_key` — transport config, resolved plain values. This
  package owns no environment variable names or settings schema of its own;
  a consumer resolves those however it already does (see `settings-base`
  for that half, if wanted).
- `extra_instructions` — appended to a fixed base tool description, never
  replacing it, for one line of consumer-specific guidance (e.g. "subject =
  the URL you fetched").

Reports are deliberately self-contained — no correlation ID, session ID, or
any other automatic link to the call that prompted the report. Nothing else
is threaded in, so the tool's own description asks the calling agent to
include whatever context makes the report useful on its own (what it was
trying to do, what it expected, what it actually ran and with what
parameters, what it got instead) — the agent's own judgment decides how
much of that is worth writing down, not a fixed field this package would
otherwise have to invent and maintain. (v0.1.0 attached FastMCP's
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
