"""mcp-result-wire contract tests — format routing + list-view projection over FastMCP."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from mcp_result_wire import FormatRoutingMiddleware, ListViewMiddleware, ListViewSettings
from page_tsv import EncodingPlan

pytestmark = pytest.mark.asyncio


async def _call(server: FastMCP, name: str, args: dict) -> Any:
    async with Client(server) as client:
        return await client.call_tool(name, args)


# --- FormatRoutingMiddleware -------------------------------------------------


async def test_page_tsv_plan_recompresses_content_for_llm() -> None:
    server = FastMCP("t")
    server.add_middleware(FormatRoutingMiddleware(plans={"page_tool": EncodingPlan("page-tsv")}, consumer="llm"))

    @server.tool(name="page_tool")
    def page_tool() -> dict:
        return {"items": [{"id": 1, "title": "a"}], "next_cursor": None}

    res = await _call(server, "page_tool", {})
    # content re-derived as a page-tsv envelope; structured_content stays the plain dict.
    envelope = json.loads(res.content[0].text)
    assert envelope["_items_format"] == "tsv"
    assert envelope["items"] == "id\ttitle\n1\ta\n"


async def test_code_consumer_does_not_compress() -> None:
    server = FastMCP("t")
    server.add_middleware(FormatRoutingMiddleware(plans={"page_tool": EncodingPlan("page-tsv")}, consumer="code"))

    @server.tool(name="page_tool")
    def page_tool() -> dict:
        return {"items": [{"id": 1, "title": "a"}], "next_cursor": None}

    res = await _call(server, "page_tool", {})
    # code consumer passes through — content is not a page-tsv envelope.
    assert "_items_format" not in res.content[0].text


async def test_json_plan_passes_through() -> None:
    server = FastMCP("t")
    server.add_middleware(FormatRoutingMiddleware(plans={"j": EncodingPlan("json")}, consumer="llm"))

    @server.tool(name="j")
    def j() -> dict:
        return {"result": {"a": 1}}

    res = await _call(server, "j", {})
    assert json.loads(res.content[0].text) == {"a": 1} or res.structured_content == {"result": {"a": 1}}


# --- ListViewMiddleware ------------------------------------------------------


async def test_list_view_projects_fields_and_paginates() -> None:
    server = FastMCP("t")
    server.add_middleware(ListViewMiddleware({"rows": ListViewSettings(default_fields=("id",), page_size=2)}))

    @server.tool(name="rows")
    def rows() -> list[dict]:
        return [{"id": 1, "extra": "x"}, {"id": 2, "extra": "y"}, {"id": 3, "extra": "z"}]

    res = await _call(server, "rows", {})
    inner = res.structured_content["result"]
    assert inner == [{"id": 1}, {"id": 2}]  # projected to id, sliced to 2


async def test_list_view_untouched_without_settings() -> None:
    server = FastMCP("t")
    server.add_middleware(ListViewMiddleware({}))

    @server.tool(name="rows")
    def rows() -> list[dict]:
        return [{"id": 1, "extra": "x"}]

    res = await _call(server, "rows", {})
    assert res.structured_content["result"] == [{"id": 1, "extra": "x"}]


async def test_format_routing_after_list_view_derives_from_projected() -> None:
    # format-routing registered first (outermost) so its content derivation runs after
    # list-view has projected structured_content.
    server = FastMCP("t")
    server.add_middleware(FormatRoutingMiddleware(plans={"rows": EncodingPlan("tsv")}, consumer="llm"))
    server.add_middleware(ListViewMiddleware({"rows": ListViewSettings(default_fields=("id",))}))

    @server.tool(name="rows")
    def rows() -> list[dict]:
        return [{"id": 1, "extra": "x"}, {"id": 2, "extra": "y"}]

    res = await _call(server, "rows", {})
    # TSV content built from the PROJECTED rows (only the id column).
    assert res.content[0].text == "id\n1\n2\n"
