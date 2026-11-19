"""Which clients can reach a server: installed (the program or app is found) and connected
(its config names the server). Driven against a temp home, never the real one."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from mcp_clients import KNOWN_CLIENTS, ClientState, McpClient, client_statuses, configured_servers

if TYPE_CHECKING:
    from pathlib import Path


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")


def _env(home: Path, programs: tuple[str, ...]) -> dict[str, str]:
    """An env whose PATH is one folder holding an executable per program name."""
    folder = home / "pathbin"
    folder.mkdir(parents=True, exist_ok=True)
    for name in programs:
        (folder / name).write_text("#!/bin/sh\n")
        (folder / name).chmod(0o755)
    return {"PATH": str(folder)}


def _states(home: Path, on_path: tuple[str, ...] = (), server: str = "srv") -> dict[str, ClientState]:
    statuses = client_statuses(server, home, env=_env(home, on_path), applications=(home / "Applications",))
    return {c.name: c.state for c in statuses}


def test_nothing_installed(tmp_path: Path) -> None:
    assert set(_states(tmp_path).values()) == {ClientState.not_installed}


def test_one_client_of_each_state(tmp_path: Path) -> None:
    _write(tmp_path / ".claude.json", {"mcpServers": {"srv": {"type": "http"}}})
    (tmp_path / "Applications" / "Claude.app").mkdir(parents=True)
    _write(tmp_path / "Library/Application Support/Claude/claude_desktop_config.json", {"preferences": {}})
    states = _states(tmp_path, ("claude",))
    assert states == {
        "Claude Code": ClientState.connected,
        "Claude Desktop": ClientState.not_connected,
        "OpenCode": ClientState.not_installed,
    }


def test_programs_in_their_install_folders_count_without_path(tmp_path: Path) -> None:
    """launchd's PATH misses ~/.local/bin and ~/.opencode/bin; a status must still see them."""
    for rel in (".local/bin/claude", ".opencode/bin/opencode"):
        _write(tmp_path / rel, "")
    states = _states(tmp_path)
    assert states["Claude Code"] is ClientState.not_connected
    assert states["OpenCode"] is ClientState.not_connected


def test_desktop_and_opencode_connected(tmp_path: Path) -> None:
    (tmp_path / "Applications" / "Claude.app").mkdir(parents=True)
    _write(tmp_path / "Library/Application Support/Claude/claude_desktop_config.json", {"mcpServers": {"srv": {}}})
    _write(tmp_path / ".config/opencode/opencode.json", {"mcp": {"srv": {"type": "remote"}}})
    states = _states(tmp_path, ("opencode",))
    assert states["Claude Desktop"] is ClientState.connected
    assert states["OpenCode"] is ClientState.connected


def test_an_unreadable_config_reads_as_not_connected(tmp_path: Path) -> None:
    _write(tmp_path / ".claude.json", "{ not json")
    assert _states(tmp_path, ("claude",))["Claude Code"] is ClientState.not_connected


def test_the_server_name_is_the_callers(tmp_path: Path) -> None:
    _write(tmp_path / ".claude.json", {"mcpServers": {"other": {}}})
    assert _states(tmp_path, ("claude",), server="srv")["Claude Code"] is ClientState.not_connected
    assert _states(tmp_path, ("claude",), server="other")["Claude Code"] is ClientState.connected


def test_a_server_table_that_is_not_an_object_names_nothing(tmp_path: Path) -> None:
    claude_code = KNOWN_CLIENTS[0]
    _write(tmp_path / ".claude.json", {"mcpServers": ["srv"]})
    assert configured_servers(claude_code, tmp_path) == {}
    _write(tmp_path / ".claude.json", ["not", "an", "object"])
    assert configured_servers(claude_code, tmp_path) == {}


def test_opencode_keys_servers_under_mcp_not_mcpservers(tmp_path: Path) -> None:
    _write(tmp_path / ".config/opencode/opencode.json", {"mcpServers": {"srv": {}}})
    assert _states(tmp_path, ("opencode",))["OpenCode"] is ClientState.not_connected


def test_order_follows_the_client_table(tmp_path: Path) -> None:
    assert [s.name for s in client_statuses("srv", tmp_path, env={}, applications=())] == [
        "Claude Code",
        "Claude Desktop",
        "OpenCode",
    ]


def test_a_caller_supplied_client(tmp_path: Path) -> None:
    editor = McpClient("Editor", config=".editor/mcp.json", servers_key="mcpServers", program="editor")
    _write(tmp_path / ".editor/mcp.json", {"mcpServers": {"srv": {}}})
    statuses = client_statuses("srv", tmp_path, env=_env(tmp_path, ("editor",)), clients=(editor,))
    assert [(s.name, s.state) for s in statuses] == [("Editor", ClientState.connected)]


def test_default_application_folders(tmp_path: Path) -> None:
    (tmp_path / "Applications" / "Claude.app").mkdir(parents=True)
    states = {s.name: s.state for s in client_statuses("srv", tmp_path, env={})}
    assert states["Claude Desktop"] is ClientState.not_connected
