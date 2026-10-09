"""Which MCP clients are on this machine, and which of them name a given server.

A client is **installed** when its program (or its macOS app) is found, and **connected**
when its own config file lists the server by name in its server table. Each client keeps
that table in a different file under a different key, and that is the knowledge this
package holds so a server does not have to.

Configs are read, never written. An absent, unreadable or malformed config reads as "names
no server": the question is asked by status displays, which must not fail because a user
hand-edited a file.

A process started by launchd (a macOS login item) gets a PATH without ``~/.local/bin`` or
``~/.opencode/bin``, so each program is also looked for in the folder its installer puts it.
"""

from __future__ import annotations

import enum
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

__all__ = ["KNOWN_CLIENTS", "ClientState", "ClientStatus", "McpClient", "client_statuses", "configured_servers"]


class ClientState(enum.StrEnum):
    connected = "connected"
    not_connected = "not_connected"
    not_installed = "not_installed"


@dataclass(frozen=True)
class McpClient:
    """Where one client lives and where it keeps its servers. Paths are relative to home.

    ``program`` is looked up on PATH and then in ``install_dir``; ``app`` is a macOS
    ``.app`` bundle name looked for in the application folders. A client names one or both.
    """

    name: str
    config: str
    servers_key: str
    program: str | None = None
    install_dir: str | None = None
    app: str | None = None


@dataclass(frozen=True)
class ClientStatus:
    name: str
    state: ClientState


#: Menu order. Claude Code and Claude Desktop key servers under ``mcpServers``; OpenCode
#: under ``mcp``.
KNOWN_CLIENTS: tuple[McpClient, ...] = (
    McpClient("Claude Code", config=".claude.json", servers_key="mcpServers", program="claude", install_dir=".local/bin"),
    McpClient(
        "Claude Desktop",
        config="Library/Application Support/Claude/claude_desktop_config.json",
        servers_key="mcpServers",
        app="Claude.app",
    ),
    McpClient("OpenCode", config=".config/opencode/opencode.json", servers_key="mcp", program="opencode", install_dir=".opencode/bin"),
)


def configured_servers(client: McpClient, home: Path) -> dict[str, object]:
    """The server table in ``client``'s config; empty when the file is absent or unreadable."""
    try:
        doc: object = json.loads((home / client.config).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    table = doc.get(client.servers_key) if isinstance(doc, dict) else None
    return table if isinstance(table, dict) else {}


def client_statuses(
    server: str,
    home: Path,
    *,
    which: Callable[[str], str | None] = shutil.which,
    applications: Sequence[Path] | None = None,
    clients: Sequence[McpClient] = KNOWN_CLIENTS,
) -> tuple[ClientStatus, ...]:
    """Each client's state for ``server``, in ``clients`` order.

    ``applications`` are the folders searched for an ``app``: ``~/Applications`` and
    ``/Applications`` by default. ``which`` is the PATH lookup, injectable for tests.
    """
    folders = applications if applications is not None else (home / "Applications", Path("/Applications"))

    def installed(client: McpClient) -> bool:
        if client.program is not None and (
            which(client.program) is not None or (client.install_dir is not None and (home / client.install_dir / client.program).exists())
        ):
            return True
        return client.app is not None and any((folder / client.app).exists() for folder in folders)

    def state(client: McpClient) -> ClientState:
        if not installed(client):
            return ClientState.not_installed
        return ClientState.connected if server in configured_servers(client, home) else ClientState.not_connected

    return tuple(ClientStatus(client.name, state(client)) for client in clients)
