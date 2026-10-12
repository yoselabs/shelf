# mcp-call

**Stop paying a second of imports to make one MCP call.** Call a tool on a Streamable HTTP MCP
server with httpx alone: no MCP SDK, no fastmcp.

```python
from mcp_call import EndpointRefused, McpEndpoint

try:
    with McpEndpoint("http://127.0.0.1:8765/mcp/", headers={"X-Token": token}) as server:
        print(server.server.version)              # what the server said in `initialize`
        result = server.call("search", {"query": "pier"})
except EndpointRefused:
    ...                                           # nothing listens there: no server is running
if result.is_error:
    print(result.text)                            # the tool's own failure, as the protocol carries it
else:
    print(result.structured)
```

For a process that starts, makes a call or two and exits: a CLI talking to the server that owns
its data, a job calling back into its host. Importing the MCP SDK costs about half a second and
fastmcp about as much again; httpx about a tenth of a second.

## The contract

- One `McpEndpoint` is one session. Entering it sends `initialize` and
  `notifications/initialized`; leaving it ends the session (`DELETE`, best effort) and closes the
  connection. `server` is the `initialize` answer: `name`, `version`, `protocol_version`,
  `instructions`.
- `call(tool, arguments)` returns a `ToolResult`: `content` (the protocol's blocks), `structured`
  (`structuredContent`), `is_error`, and `text` (the text blocks joined). A failure the tool
  reports is `is_error=True`, never an exception.
- `tools()` lists every tool, following `nextCursor`.
- A reply may be a JSON body or an SSE stream (the server chooses, e.g. fastmcp's
  `json_response`); both are read, and messages on the stream that answer no request of ours are
  skipped. The session header is sent back when the server issues one, so stateless servers work
  too.
- Failures: `EndpointRefused` when nothing accepts the connection; `McpCallError` for an HTTP error
  status (`.status`), a JSON-RPC error (`.code`, `.data`), or a reply with no answer.
- Sync only: the callers it was made for are sync. Not covered: server-initiated requests
  (sampling, elicitation) and resumable streams.
