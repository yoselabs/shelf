# mcp-arg-errors

Every failed FastMCP tool call as an error an agent can act on: whatever the tool body
raised (`ErrorWire`), and arguments that do not fit the tool's schema
(`ArgumentErrorMiddleware`).

## Whatever the body raised: `ErrorWire`

FastMCP masks an exception escaping a tool body before any middleware sees it, so the
conversion happens at the tool boundary. `ErrorWire.guard` wraps each tool function; a
failure comes back as an `is_error` result with `{"error": <envelope>}` in
`structured_content` and text rendered from the same envelope.

```python
from a2effect import UnexpectedDefect
from mcp_arg_errors import ArgumentErrorMiddleware, ErrorWire

wire = ErrorWire(UnexpectedDefect, trace_id=trace_of, logger=log)
server.add_tool(FunctionTool.from_function(wire.guard(verb, drop_params={"attach"}), name="create"))
server.add_middleware(ArgumentErrorMiddleware(lambda fault: wire.result(to_typed(fault))))
```

- **A typed error renders as itself.** Typed means a `kind` and `to_envelope_dict()`; an
  `a2effect` `AppError` is one, and the package does not import a2effect.
- **Anything else is a defect.** It is logged with a trace id and the caller gets
  `defect("internal error; trace_id=…")` with the id in `details`, never the original
  exception's text. A typed error of kind `bug` keeps its own envelope and gains the id.
- **The text is the consumer's.** Default `envelope_text`: message, `Hint:`, and `Details:`
  as JSON cut at `DETAILS_CHARS` (some clients show only the text of a failed call).
  Pass `text=(error, envelope) -> str` for another form.
- `drop_params` removes a parameter from the advertised schema on that binding and strips
  it from the call. `passthrough` re-raises exception types the author already shaped for
  the wire (`fastmcp.exceptions.ToolError`).

## Arguments that do not fit the schema: `ArgumentErrorMiddleware`

FastMCP validates arguments before a tool body runs, so `ErrorWire` never
sees that failure, and the client gets pydantic's text with no next step.
`ArgumentErrorMiddleware` catches it and hands your renderer an `ArgumentFault`:

```python
from mcp_arg_errors import ArgumentErrorMiddleware, ArgumentFault

def render(fault: ArgumentFault) -> ToolResult:
    # fault.tool, fault.argument, fault.reason, fault.unknown, fault.message, fault.hint
    return my_error_result(code="unknown_argument" if fault.unknown else "invalid_argument", ...)

server.add_middleware(ArgumentErrorMiddleware(render))
```

## A stale tool list

A client caches the tool list when it connects. When the server later drops a parameter, the
client keeps sending it, often as a default the agent never chose, and every call fails.
An argument the tool does not have is `unknown`, with a hint telling the agent to reconnect
the server (`/mcp` in Claude Code). The server never accepts the removed argument: that
would keep the backward compatibility the schema change ended.

When a call has several faults, the unknown argument is the one reported: a stale client's
other errors come from the same stale schema.

## Sharp edges

- Needs `fastmcp>=3.4` (`ToolResult(is_error=True)`).
- Only failures FastMCP raises as a pydantic `ValidationError` are caught; everything else
  passes through to the server's own handling.
