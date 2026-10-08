# mcp-arg-errors

FastMCP middleware for tool calls whose arguments do not fit the tool's schema.

FastMCP validates arguments before a tool body runs, so a server's own error handling never
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
