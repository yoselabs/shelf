# mcp-feedback

A drop-in, agent-invoked feedback tool for any FastMCP server. Mounts a single
`report_feedback(subject, note, wanted=None)` tool with a **fixed schema** —
the whole point is one identical shape everywhere, not a customizable one.

```python
from fastmcp import FastMCP
from mcp_feedback import register_feedback_tool

server = FastMCP("my-server")
register_feedback_tool(
    server,
    endpoint="https://feedback-gateway.example.net/v1/logs",
    api_key="...",
    extra_instructions="subject = the URL you fetched.",
)
```

## Exactly two consumer knobs

- `endpoint` / `api_key` — plain, already-resolved transport config. This
  package owns no environment variable names or settings schema; resolve
  those however your own project already does (`settings-base`, if you want
  a shared way to do that too).
- `extra_instructions` — appended to a fixed base tool description, never
  replacing it. One line of domain-specific guidance, nothing more.

Everything else — the tool name, its three parameters (`subject: str`,
`note: str`, `wanted: str | None`), the absence of any closed category, the
OTLP/HTTP-logs transport, the `sent: bool` result shape — is identical no
matter who mounts it.

## Reports are self-contained, on purpose

No correlation ID, no session ID, nothing automatically links a report back
to the call that prompted it. The tool's own description asks the calling
agent to write a report that stands on its own — what it was trying to do,
what it expected, what it actually ran and with which parameters, what it
got instead, and anything it would have liked even as a minor nice-to-have.
The agent decides how much of that is worth including; this package doesn't
force a fixed field for it.

This also means the tool's underlying function needs no live MCP
request/session to run — v0.1.0 attached FastMCP's `ctx.session_id` for
correlation, which made the function require one, breaking any consumer
that calls tool functions directly outside of a real session (a consumer's
own CLI, concretely). Reversed in v0.2.0.

## Transport

Hand-rolled async `httpx` POST of an OTLP/HTTP-logs JSON payload
(`resourceLogs[].scopeLogs[].logRecords[]`), 5s timeout, `X-Api-Key` header.
Delivery failures are logged, never raised — `sent` reflects whether a send
was *attempted* (endpoint + key both configured), never whether it was
confirmed delivered. Deliberately not the OTel Logs SDK: `opentelemetry.sdk
._logs` is unstable/private in the Python SDK, and its exporter is
synchronous.

## What this package will not do

- No closed category/severity field for the caller to self-classify into —
  free text only. (A simpler, narrower value than any taxonomy — a plain
  `severity` string on an unrelated project — already drifted into five
  different casings once real callers touched it; a forced taxonomy here
  would drift the same way, with a worse failure mode: an agent under
  pressure picks the closest bucket, not the right one.)
- No per-consumer field additions or renames. A consumer that needs a
  genuinely different shape should question whether it's still "feedback" in
  this package's sense, not fork the schema.
