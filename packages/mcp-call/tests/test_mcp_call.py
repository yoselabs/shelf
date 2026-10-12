"""mcp-call contract tests: a real FastMCP server over a real socket, in each reply mode a server
may choose (SSE or JSON bodies; a session or none), called as a short-lived process would."""

from __future__ import annotations

import asyncio
import socket
import subprocess
import sys

import pytest
from async_scope.asgi import serve_asgi
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from mcp_call import EndpointRefused, McpCallError, McpEndpoint, ServerInfo, ToolResult

# Every way a FastMCP server may answer: SSE or JSON bodies (`json_response`), with a session
# or stateless (`stateless_http`).
MODES = [
    pytest.param(False, False, id="sse-session"),
    pytest.param(True, False, id="json-session"),
    pytest.param(True, True, id="json-stateless"),
    pytest.param(False, True, id="sse-stateless"),
]


def _server() -> FastMCP:
    server = FastMCP("harbor", version="4.2.0", instructions="Ask about the harbor.")

    @server.tool
    def berth(pier: int) -> dict[str, object]:
        """Which berth a pier opens."""
        return {"pier": pier, "berth": f"B{pier * 2}"}

    @server.tool
    def headers() -> dict[str, str]:
        found = get_http_headers(include_all=True)
        return {k: v for k, v in found.items() if k.startswith("x-")}

    @server.tool
    def closed() -> str:
        msg = "the harbor is closed"
        raise ToolError(msg)

    return server


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.mark.asyncio
@pytest.mark.parametrize(("json_response", "stateless_http"), MODES)
async def test_a_call_returns_the_tools_structured_and_text_result(json_response: bool, stateless_http: bool) -> None:
    async with serve_asgi(_server().http_app(json_response=json_response, stateless_http=stateless_http)) as base:

        def run() -> tuple[ServerInfo, ToolResult, ToolResult, list[str]]:
            with McpEndpoint(f"{base}/mcp/", headers={"X-Token": "t1"}) as server:
                result = server.call("berth", {"pier": 4})
                return server.server, result, server.call("headers"), [t["name"] for t in server.tools()]

        info, result, headers, tools = await asyncio.to_thread(run)

    assert (info.name, info.version, info.instructions) == ("harbor", "4.2.0", "Ask about the harbor.")
    assert result.structured == {"pier": 4, "berth": "B8"}
    assert '"berth":"B8"' in result.text.replace(" ", "")
    assert result.is_error is False
    assert headers.structured == {"x-token": "t1"}
    assert sorted(tools) == ["berth", "closed", "headers"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("json_response", "stateless_http"), MODES)
async def test_a_tools_own_failure_is_a_result_not_an_exception(json_response: bool, stateless_http: bool) -> None:
    async with serve_asgi(_server().http_app(json_response=json_response, stateless_http=stateless_http)) as base:

        def run() -> ToolResult:
            with McpEndpoint(f"{base}/mcp/") as server:
                return server.call("closed")

        result = await asyncio.to_thread(run)

    assert result.is_error is True
    assert "the harbor is closed" in result.text


@pytest.mark.asyncio
async def test_bad_arguments_are_the_servers_answer_not_a_crash() -> None:
    async with serve_asgi(_server().http_app()) as base:

        def run() -> ToolResult:
            with McpEndpoint(f"{base}/mcp/") as server:
                return server.call("berth", {"pier": "four"})

        result = await asyncio.to_thread(run)

    assert result.is_error is True


def test_nothing_listening_is_endpoint_refused() -> None:
    with pytest.raises(EndpointRefused), McpEndpoint(f"http://127.0.0.1:{_free_port()}/mcp/"):
        pass


@pytest.mark.asyncio
async def test_a_path_with_no_server_is_an_http_error_naming_the_status() -> None:
    async with serve_asgi(_server().http_app()) as base:

        def run() -> None:
            with McpEndpoint(f"{base}/elsewhere/"):
                pass

        with pytest.raises(McpCallError) as caught:
            await asyncio.to_thread(run)

    assert caught.value.status == 404
    assert not isinstance(caught.value, EndpointRefused)


def test_a_call_outside_the_session_says_to_open_it() -> None:
    endpoint = McpEndpoint("http://127.0.0.1:9/mcp/")
    with pytest.raises(McpCallError, match="not open"):
        endpoint.call("berth")
    with pytest.raises(McpCallError, match="not open"):
        _ = endpoint.server


def test_importing_it_loads_neither_the_mcp_sdk_nor_fastmcp() -> None:
    probe = "import sys, mcp_call; print(sorted(m for m in ('mcp', 'fastmcp') if m in sys.modules))"
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]"
