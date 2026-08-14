"""mcp-feedback contract tests — the fixed report_feedback tool over FastMCP."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastmcp import Client, FastMCP
from mcp_feedback import register_feedback_tool

pytestmark = pytest.mark.asyncio


class _RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, response: httpx.Response) -> None:
        self.requests: list[httpx.Request] = []
        self._response = response

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._response


def _server_with_recording_transport(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> tuple[FastMCP, _RecordingTransport]:
    transport = _RecordingTransport(httpx.Response(200, json={"partialSuccess": {}}))
    real_client_cls = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client_cls(**kw, transport=transport))
    server = FastMCP("t")
    register_feedback_tool(server, **kwargs)
    return server, transport


async def _call(server: FastMCP, args: dict) -> Any:
    async with Client(server) as client:
        return await client.call_tool("report_feedback", args)


async def test_two_independent_registrations_produce_identical_schema() -> None:
    server_a = FastMCP("a")
    register_feedback_tool(server_a, endpoint="https://a.example/logs", api_key="key-a")
    server_b = FastMCP("b")
    register_feedback_tool(server_b, endpoint="https://b.example/logs", api_key="key-b", extra_instructions="subject = the ticket ID.")

    async with Client(server_a) as client_a, Client(server_b) as client_b:
        tools_a = await client_a.list_tools()
        tools_b = await client_b.list_tools()

    assert tools_a[0].name == tools_b[0].name == "report_feedback"
    assert tools_a[0].inputSchema == tools_b[0].inputSchema


async def test_no_closed_category_in_schema() -> None:
    server = FastMCP("t")
    register_feedback_tool(server, endpoint="https://gateway.test/logs", api_key="k")

    async with Client(server) as client:
        tools = await client.list_tools()

    props = tools[0].inputSchema["properties"]
    assert set(props) == {"subject", "note", "wanted"}
    for field in props.values():
        assert "enum" not in field


async def test_extra_instructions_appends_to_base_description() -> None:
    server = FastMCP("t")
    register_feedback_tool(server, endpoint="https://gateway.test/logs", api_key="k", extra_instructions="subject = the URL you fetched.")

    async with Client(server) as client:
        tools = await client.list_tools()

    assert "No category to pick" in tools[0].description  # base text present
    assert "subject = the URL you fetched." in tools[0].description  # appended text present


async def test_extra_instructions_omitted_leaves_only_base_text() -> None:
    server = FastMCP("t")
    register_feedback_tool(server, endpoint="https://gateway.test/logs", api_key="k")

    async with Client(server) as client:
        tools = await client.list_tools()

    assert "No category to pick" in tools[0].description


async def test_report_is_sent_and_carries_subject_note_wanted(monkeypatch: pytest.MonkeyPatch) -> None:
    server, transport = _server_with_recording_transport(monkeypatch, endpoint="https://gateway.test/logs", api_key="secret-key")

    res = await _call(server, {"subject": "https://example.com/x", "note": "wrong item", "wanted": "the RTX 4090 listing"})

    assert res.structured_content["sent"] is True
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request.headers["x-api-key"] == "secret-key"
    body = json.loads(request.content)
    record = body["resourceLogs"][0]["scopeLogs"][0]
    assert record["scope"]["name"] == "mcp.feedback.agent"
    attrs = {a["key"]: a["value"]["stringValue"] for a in record["logRecords"][0]["attributes"]}
    assert attrs["subject"] == "https://example.com/x"
    assert attrs["note"] == "wrong item"
    assert attrs["wanted"] == "the RTX 4090 listing"


async def test_no_correlation_id_is_attached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reports are self-contained (v0.2.0) — no session_id, no report_id,
    nothing beyond what the caller explicitly supplied."""
    server, transport = _server_with_recording_transport(monkeypatch, endpoint="https://gateway.test/logs", api_key="k")

    await _call(server, {"subject": "s", "note": "n"})

    body = json.loads(transport.requests[0].content)
    attrs = {a["key"] for a in body["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]["attributes"]}
    assert attrs == {"subject", "note"}


async def test_tool_function_callable_without_a_live_mcp_session() -> None:
    """The whole point of dropping Context (v0.2.0): the underlying function
    must be callable directly, the way a consumer's own CLI would call it —
    not only through a real MCP request/session."""
    server = FastMCP("t")
    register_feedback_tool(server, endpoint="", api_key="")
    tool = await server.get_tool("report_feedback")
    fn = getattr(tool, "fn", None)
    assert fn is not None

    result = await fn(subject="s", note="n")

    assert result.sent is False


async def test_wanted_omitted_when_not_supplied(monkeypatch: pytest.MonkeyPatch) -> None:
    server, transport = _server_with_recording_transport(monkeypatch, endpoint="https://gateway.test/logs", api_key="k")

    await _call(server, {"subject": "s", "note": "n"})

    body = json.loads(transport.requests[0].content)
    attrs = {a["key"] for a in body["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]["attributes"]}
    assert "wanted" not in attrs


async def test_not_configured_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: (_ for _ in ()).throw(AssertionError("no client should be built")))
    server = FastMCP("t")
    register_feedback_tool(server, endpoint="", api_key="")

    res = await _call(server, {"subject": "s", "note": "n"})

    assert res.structured_content["sent"] is False
