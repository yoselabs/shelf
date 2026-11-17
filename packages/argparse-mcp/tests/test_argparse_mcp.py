"""argparse-mcp over a real FastMCP server and client."""

from __future__ import annotations

import argparse

import pytest
from argparse_mcp import tools_from_parser
from fastmcp import Client, FastMCP

pytestmark = pytest.mark.asyncio


def build_server(name: str, parser: argparse.ArgumentParser, run, *, usage: int = 2) -> FastMCP:
    server = FastMCP(name, instructions=parser.description)
    for tool in tools_from_parser(parser, run, usage=usage):
        server.add_tool(tool)
    return server


def _parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="t", description="the t tool")
    top.add_argument("--repo", help="repository")
    top.add_argument("--rev")
    sub = top.add_subparsers(dest="cmd", required=True)
    show = sub.add_parser("show", description="Show an item.")
    show.add_argument("address", help="what to show")
    show.add_argument("--format", choices=["text", "json"], default="text")
    show.add_argument("--verbose", action="store_true")
    show.add_argument("--tag", action="append")
    show.add_argument("--limit", type=int)
    words = sub.add_parser("words")
    words.add_argument("words", nargs="*")
    words.add_argument("--repo")  # own option wins over the shared one
    return top


def _run(calls: list[list[str]]):
    parser = _parser()

    def run(argv: list[str]) -> tuple[int, list[str]]:
        calls.append(argv)
        args = parser.parse_args(argv)  # may SystemExit(2)
        return 0, [f"ok {args.cmd}"]

    return run


async def test_one_tool_per_subcommand_with_schema() -> None:
    server = build_server("t", _parser(), _run([]))
    async with Client(server) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert set(tools) == {"show", "words"}
    props = tools["show"].inputSchema["properties"]
    assert set(props) == {"address", "format", "verbose", "tag", "limit", "repo", "rev"}  # globals folded in
    assert tools["show"].inputSchema["required"] == ["address"]
    assert tools["show"].description == "Show an item."
    assert props["format"]["anyOf"][0]["enum"] == ["text", "json"]
    assert props["verbose"]["anyOf"][0]["type"] == "boolean"
    assert props["limit"]["anyOf"][0]["type"] == "integer"
    assert "default text" in props["format"]["anyOf"][0]["description"]
    assert set(tools["words"].inputSchema["properties"]) == {"words", "repo", "rev"}


async def test_call_rebuilds_argv_in_order() -> None:
    calls: list[list[str]] = []
    async with Client(build_server("t", _parser(), _run(calls))) as client:
        out = await client.call_tool(
            "show", {"address": "a#b", "format": "json", "verbose": True, "tag": ["x", "y"], "limit": 3, "repo": "/r"}
        )
    assert calls == [["--repo", "/r", "show", "--format", "json", "--verbose", "--tag", "x", "--tag", "y", "--limit", "3", "a#b"]]
    assert out.structured_content == {"exit_code": 0, "output": "ok show"}


async def test_positional_list_and_own_option_wins() -> None:
    calls: list[list[str]] = []
    async with Client(build_server("t", _parser(), _run(calls))) as client:
        await client.call_tool("words", {"words": ["a", "b"], "repo": "/r", "rev": "HEAD"})
    assert calls == [["--rev", "HEAD", "words", "--repo", "/r", "a", "b"]]


async def test_systemexit_becomes_usage_result() -> None:
    calls: list[list[str]] = []
    run = _run(calls)

    def broken(argv: list[str]) -> tuple[int, list[str]]:
        return run([*argv, "--nope"])

    async with Client(build_server("t", _parser(), broken)) as client:
        out = await client.call_tool("words", {"words": []})
    assert out.structured_content is not None
    assert out.structured_content["exit_code"] == 2
    assert "unrecognized arguments: --nope" in out.structured_content["output"]


async def test_exit_code_and_lines_pass_through_and_usage_is_configurable() -> None:
    def run(argv: list[str]) -> tuple[int, list[str]]:
        if argv[0] == "words":
            raise SystemExit(2)
        return 1, ["finding 1", "finding 2"]

    parser = _parser()
    server = build_server("t", parser, run, usage=64)
    async with Client(server) as client:
        found = await client.call_tool("show", {"address": "x"})
        bad = await client.call_tool("words", {})
    assert found.structured_content == {"exit_code": 1, "output": "finding 1\nfinding 2"}
    assert bad.structured_content == {"exit_code": 64, "output": "usage error (2)"}


async def test_tools_from_parser_returns_tools_without_a_server() -> None:
    assert [t.name for t in tools_from_parser(_parser(), _run([]))] == ["show", "words"]
