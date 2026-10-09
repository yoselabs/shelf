# mcp-bridge

A stdio MCP server that relays every request to a Streamable HTTP MCP server, for clients that can
only start a local program (Claude Desktop's Chat tab cannot reach an HTTP server, and its
connectors run in Anthropic's cloud, so they cannot reach `127.0.0.1` either).

```python
from mcp_bridge import build_bridge, downstream_client_name

def headers() -> dict[str, str]:
    sent = {"X-Token": read_token()}
    if (name := downstream_client_name()) is not None:
        sent["X-Client"] = name
    return sent

build_bridge("http://127.0.0.1:8000/mcp/", headers=headers).run(transport="stdio", show_banner=False)
```

It wraps FastMCP's proxy, which opens a fresh server session per request, so a server restart
never strands the client. A call made while the server refuses connections waits up to `wait`
seconds (60 by default) and then goes through; a refused token or any other failure returns at
once.

Compared with `mcp-remote` (npm): no Node needed, and the restart wait, which `mcp-remote` does not
document.

## Sharp edges

- stdout is the MCP channel: write diagnostics to stderr.
- Starting the server when it is down is the consumer's job (a2kay asks launchd).
