"""mcp-arg-errors contract tests over a real FastMCP server and client."""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client, FastMCP
from fastmcp.tools import ToolResult
from mcp.types import TextContent
from mcp_arg_errors import STALE_TOOL_LIST_HINT, ArgumentErrorMiddleware, ArgumentFault

pytestmark = pytest.mark.asyncio


def _server(seen: list[ArgumentFault]) -> FastMCP:
    def render(fault: ArgumentFault) -> ToolResult:
        seen.append(fault)
        text = f"{fault.message} | {fault.hint}"
        return ToolResult(content=[TextContent(type="text", text=text)], is_error=True)

    server = FastMCP("t")
    server.add_middleware(ArgumentErrorMiddleware(render))

    @server.tool(name="update")
    def update(ref: str, version: str, fields: dict[str, Any] | None = None) -> dict[str, str]:
        return {"ref": ref, "version": version}

    @server.tool(name="boom")
    def boom() -> str:
        msg = "not an argument failure"
        raise RuntimeError(msg)

    return server


async def _call(server: FastMCP, name: str, args: dict[str, Any]) -> Any:
    async with Client(server) as client:
        return await client.call_tool(name, args, raise_on_error=False)


async def test_an_argument_the_tool_does_not_have_says_the_tool_list_is_stale() -> None:
    seen: list[ArgumentFault] = []

    res = await _call(_server(seen), "update", {"ref": "a", "version": "1", "unset": None})

    assert res.is_error
    assert seen == [ArgumentFault(tool="update", argument="unset", reason=seen[0].reason, unknown=True)]
    assert seen[0].message == "update has no argument 'unset'"
    assert seen[0].hint == STALE_TOOL_LIST_HINT
    assert "/mcp" in res.content[0].text


async def test_an_unknown_argument_wins_over_a_missing_one() -> None:
    seen: list[ArgumentFault] = []

    await _call(_server(seen), "update", {"ref": "a", "unset": ["x"]})

    assert (seen[0].argument, seen[0].unknown) == ("unset", True)


async def test_a_missing_argument_is_named_without_the_stale_hint() -> None:
    seen: list[ArgumentFault] = []

    await _call(_server(seen), "update", {"ref": "a"})

    assert (seen[0].argument, seen[0].unknown, seen[0].hint) == ("version", False, None)
    assert seen[0].message.startswith("version: ")


async def test_a_wrong_type_is_named() -> None:
    seen: list[ArgumentFault] = []

    await _call(_server(seen), "update", {"ref": "a", "version": "1", "fields": "not a mapping"})

    assert (seen[0].argument, seen[0].unknown) == ("fields", False)


async def test_a_valid_call_and_other_failures_pass_through() -> None:
    seen: list[ArgumentFault] = []
    server = _server(seen)

    ok = await _call(server, "update", {"ref": "a", "version": "1"})
    failed = await _call(server, "boom", {})

    assert not ok.is_error
    assert failed.is_error
    assert seen == []
