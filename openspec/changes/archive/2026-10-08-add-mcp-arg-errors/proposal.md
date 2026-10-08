## Why

A FastMCP server validates a call's arguments before the tool body runs, so the server's own
error handling never sees the failure and the client gets pydantic's text with no next step.
a2kay wrote a middleware for that. Then removing `update.unset` froze every running agent: each
client still had the old schema cached, sent `unset` on every call, and got "Unexpected keyword
argument" with nothing saying the fix is to reconnect. The owner ruled out accepting removed
arguments, so the fix is the error, and every FastMCP server that changes its schema needs it.

## What Changes

- New package `mcp-arg-errors`: `ArgumentErrorMiddleware(render)` hands the consumer an
  `ArgumentFault` (tool, argument, reason, unknown, message, hint) for any argument-schema failure;
  other failures pass through.
- An argument the tool does not have is `unknown`, with a hint to reconnect the MCP server, and is
  reported in preference to the call's other faults.

## Impact

- New catalog entry, a2kay use case, ledger delivery. a2kay replaces its own middleware with it.
