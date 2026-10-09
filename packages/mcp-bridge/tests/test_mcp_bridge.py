"""mcp-bridge contract tests: a real HTTP MCP server behind the bridge, called as a client would."""

from __future__ import annotations

import asyncio
import socket

import pytest
from async_scope.asgi import serve_asgi
from fastmcp import Client, FastMCP
from fastmcp.server.dependencies import get_http_headers
from mcp.shared.exceptions import McpError
from mcp.types import Implementation
from mcp_bridge import build_bridge, downstream_client_name

pytestmark = pytest.mark.asyncio


def _server() -> FastMCP:
    server = FastMCP("upstream")

    @server.tool(name="whoami")
    def whoami() -> dict[str, str]:
        headers = get_http_headers(include_all=True)
        return {k: v for k, v in headers.items() if k.startswith("x-")}

    return server


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def test_the_bridge_relays_the_servers_tools_with_its_headers() -> None:
    async with serve_asgi(_server().http_app()) as base:
        bridge = build_bridge(f"{base}/mcp/", headers={"X-Token": "t1"})
        async with Client(bridge) as client:
            tools = [t.name for t in await client.list_tools()]
            result = await client.call_tool("whoami", {})

    assert tools == ["whoami"]
    assert result.data == {"x-token": "t1"}


async def test_headers_are_computed_per_request_and_can_name_the_client() -> None:
    def headers() -> dict[str, str]:
        name = downstream_client_name()
        return {"X-Client": name} if name else {}

    async with serve_asgi(_server().http_app()) as base:
        bridge = build_bridge(f"{base}/mcp/", headers=headers)
        async with Client(bridge, client_info=Implementation(name="claude-code", version="1")) as client:
            result = await client.call_tool("whoami", {})

    assert result.data == {"x-client": "claude-code"}


async def test_a_call_during_a_restart_waits_for_the_server() -> None:
    port = _free_port()
    bridge = build_bridge(f"http://127.0.0.1:{port}/mcp/", wait=20.0)
    client = Client(bridge)
    async with serve_asgi(_server().http_app(), port=port):
        await client.__aenter__()
        assert not (await client.call_tool("whoami", {}, raise_on_error=False)).is_error

    async def come_back() -> None:
        await asyncio.sleep(1.5)
        async with serve_asgi(_server().http_app(), port=port):
            await asyncio.sleep(4)

    back = asyncio.create_task(come_back())
    result = await client.call_tool("whoami", {}, raise_on_error=False)
    await back
    await client.__aexit__(None, None, None)

    assert not result.is_error, result.content


async def test_a_server_that_stays_down_fails_after_the_wait() -> None:
    """Initialize is relayed too, so a bridge whose server never answers fails at connect."""
    bridge = build_bridge(f"http://127.0.0.1:{_free_port()}/mcp/", wait=1.0)
    loop = asyncio.get_running_loop()
    started = loop.time()

    with pytest.raises(McpError, match="connect"):
        async with Client(bridge):
            pass

    assert 1.0 <= loop.time() - started < 10
