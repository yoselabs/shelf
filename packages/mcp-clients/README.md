# mcp-clients

**Stop caring where each MCP client keeps its server list.** Ask which clients are on
this machine and which of them already name your server.

```python
from mcp_clients import ClientState, client_statuses

for status in client_statuses("my-server", Path.home()):
    print(status.name, status.state)      # Claude Code connected / OpenCode not_installed / ...
```

| Client | Installed when | Config (under home) | Servers key |
| --- | --- | --- | --- |
| Claude Code | `claude` on PATH or in `~/.local/bin` | `.claude.json` | `mcpServers` |
| Claude Desktop | `Claude.app` in `~/Applications` or `/Applications` | `Library/Application Support/Claude/claude_desktop_config.json` | `mcpServers` |
| OpenCode | `opencode` on PATH or in `~/.opencode/bin` | `.config/opencode/opencode.json` | `mcp` |

## Rules

- **Read, never written.** Connecting a client is the caller's job.
- **A bad config is "not connected", not an error.** Absent, unreadable, not JSON, or a
  server table that is not an object: the client names no server. Status displays must
  not fail because someone hand-edited a file.
- **Installer folders count.** A launchd login item gets a PATH without `~/.local/bin`
  or `~/.opencode/bin`; each program is also looked for where its installer puts it.
- `which`, `applications` and `clients` are injectable; pass your own `McpClient` rows to
  check a client this table does not know yet. `ClientState` values are plain words —
  the display text is the caller's.
