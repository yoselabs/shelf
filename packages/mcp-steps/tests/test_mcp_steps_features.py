"""mcp-steps, stated as Gherkin, against an in-memory FastMCP server."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, override

import pytest
from fastmcp import Client, Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import ToolResult
from mcp.types import TextContent
from mcp_steps import McpSessions
from mcp_steps.steps import *  # noqa: F403 — the shipped step, registered here
from pytest_bdd import given, parsers, scenarios, then, when

if TYPE_CHECKING:
    from collections.abc import Iterator

scenarios("features/sessions.feature")


def _server() -> FastMCP:
    server = FastMCP("probe")
    counter = {"n": 0}

    @server.tool
    def echo(said: str) -> dict[str, str]:
        return {"said": said}

    @server.tool
    def count() -> dict[str, int]:
        counter["n"] += 1
        return {"count": counter["n"]}

    @server.tool
    def session(ctx: Context) -> dict[str, int]:
        return {"session": id(ctx.session)}

    @server.tool
    def refuse(code: str) -> dict[str, str]:
        raise ToolError(json.dumps({"error": {"code": code, "message": "refused"}}))

    @server.tool
    def refuse_plainly() -> dict[str, str]:
        msg = "nothing to do"
        raise ToolError(msg)

    @server.tool
    def notice() -> ToolResult:
        return ToolResult(
            content=[TextContent(type="text", text="{}"), TextContent(type="text", text="the vault is read-only")],
            structured_content={"ok": True},
        )

    return server


class _Suite(McpSessions):
    fills: dict[str, str]

    @override
    def prepare(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        return {k: self.fills.get(v, v) if isinstance(v, str) else v for k, v in args.items()}


@pytest.fixture
def mcp_world() -> Iterator[_Suite]:
    with asyncio.Runner() as runner:
        holder: dict[str, FastMCP] = {}
        world = _Suite(runner, connect=lambda _actor: Client(holder["server"]))
        world.fills = {}
        holder["server"] = _server()
        yield world
        world.close()


@pytest.fixture
def seen() -> dict[str, Any]:
    return {}


@given("a server with a counter, an echo and a tool that refuses")
def _server_given(mcp_world: _Suite) -> None:
    assert mcp_world.sessions == {}


@given(parsers.parse('the suite fills "{name}" with "{value}"'))
def _fills(mcp_world: _Suite, name: str, value: str) -> None:
    mcp_world.fills[name] = value


@when(parsers.parse('an observer asks "{tool}" with code "{code}"'))
def _asks(mcp_world: _Suite, seen: dict[str, Any], tool: str, code: str) -> None:
    seen["result"], seen["refusal"] = mcp_world.ask(tool, {"code": code}, actor="observer")


@then(parsers.parse('the result holds "{key}" = "{value}"'))
def _holds(mcp_world: _Suite, key: str, value: str) -> None:
    assert mcp_world.last is not None, mcp_world.error
    assert str(mcp_world.last[key]) == value


@then("the result has no notices")
def _no_notices(mcp_world: _Suite) -> None:
    assert mcp_world.last is not None
    assert mcp_world.last["notices"] == []


@then(parsers.parse('the result\'s notices are "{text}"'))
def _notices(mcp_world: _Suite, text: str) -> None:
    assert mcp_world.last is not None
    assert mcp_world.last["notices"] == [text]


@then("there is no refusal")
def _no_refusal(mcp_world: _Suite) -> None:
    assert mcp_world.error is None


@then("there is no result")
def _no_result(mcp_world: _Suite) -> None:
    assert mcp_world.last is None


@then(parsers.parse('the refusal\'s {field} is "{value}"'))
def _refusal(mcp_world: _Suite, field: str, value: str) -> None:
    assert mcp_world.error is not None, mcp_world.last
    assert mcp_world.error[field] == value


@then("the agent and someone else hold different sessions")
def _different(mcp_world: _Suite) -> None:
    ids = set()
    for actor in ("the agent", "someone else"):
        out, _ = mcp_world.ask("session", {}, actor=actor)
        assert out is not None
        ids.add(out["session"])
    assert len(ids) == 2


@then(parsers.parse('the observer saw the refusal "{code}"'))
def _observer(seen: dict[str, Any], code: str) -> None:
    assert seen["result"] is None
    assert seen["refusal"]["code"] == code
