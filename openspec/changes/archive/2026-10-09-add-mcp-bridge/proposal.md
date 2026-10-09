## Why

Claude Desktop's Chat tab can only start a local program speaking MCP over stdio: its connectors
run in Anthropic's cloud and cannot reach 127.0.0.1, and its config takes no URL. a2kay wrote
`a2kay bridge` for that; the generic part (relay, headers, surviving a restart) is any HTTP MCP
server's need. The common alternative, mcp-remote, needs system Node and documents no restart handling.

## What Changes

- New package `mcp-bridge`: `build_bridge(url, headers=..., wait=60)` returns a FastMCP proxy
  served over stdio, with headers per request, a fresh server session per call, and a call made
  while the server refuses connections held up to `wait` seconds. `downstream_client_name()` names
  the stdio client inside a request.

## Impact

- New catalog entry, a2kay use case, ledger delivery. a2kay's bridge keeps only its own parts.
