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

Reports carry `ctx.session_id` (FastMCP's own per-client-session identifier)
as their only correlation signal, beyond timestamp proximity. This is an
explicit stopgap: no MCP-protocol mechanism exists today to link a later
tool call back to a specific earlier one. This package is meant to be
migrated off session-only correlation once/if MCP ships a native
call-linking or feedback mechanism — not extended with a home-grown
correlation ID scheme in the meantime.

Delivery is OTLP/HTTP-logs over a hand-rolled async `httpx` POST — not the
OTel Logs SDK (`opentelemetry.sdk._logs` is unstable/private in the Python
SDK, and its exporter is synchronous). Best-effort and non-blocking: a
delivery failure is logged, never raised, and `sent` on the result reflects
whether a send was attempted, never whether it was confirmed delivered.
"""

from __future__ import annotations

from mcp_feedback._tool import FeedbackReportResult, register_feedback_tool

__all__ = ["FeedbackReportResult", "register_feedback_tool"]
