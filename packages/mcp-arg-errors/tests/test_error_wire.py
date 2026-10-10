"""ErrorWire over a real FastMCP server and client: every failure leaves as one error result."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import FunctionTool
from mcp_arg_errors import DETAILS_CHARS, ArgumentErrorMiddleware, ArgumentFault, ErrorWire, TypedError, envelope_text

if TYPE_CHECKING:
    import pytest


class Refused(Exception):  # noqa: N818 — a stand-in typed error, shaped like a2effect's AppError
    kind: ClassVar[str] = "input"

    def __init__(self, message: str, *, hint: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.hint = hint
        self.details = details or {}

    def to_envelope_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "code": "refused", "message": str(self), "hint": self.hint, "details": dict(self.details)}


class Defect(Refused):
    kind: ClassVar[str] = "bug"


def _wire(**kw: Any) -> ErrorWire:
    return ErrorWire(Defect, trace_id=lambda _e: "t-1", **kw)


def _server(wire: ErrorWire) -> FastMCP:
    server = FastMCP("t")

    async def refuse(name: str) -> str:
        msg = f"no {name}"
        raise Refused(msg, hint="try another", details={"name": name})

    async def crash() -> str:
        msg = "secret path /home/x"
        raise RuntimeError(msg)

    async def typed_bug() -> str:
        msg = "an invariant broke"
        raise Defect(msg, details={"where": "here"})

    async def shaped() -> str:
        msg = "already wire-shaped"
        raise ToolError(msg)

    async def echo(name: str, secret: str = "") -> dict[str, str]:
        return {"name": name, "secret": secret}

    for fn in (refuse, crash, typed_bug, shaped):
        server.add_tool(FunctionTool.from_function(wire.guard(fn), name=fn.__name__))
    server.add_tool(FunctionTool.from_function(wire.guard(echo, drop_params=frozenset({"secret"})), name="echo"))

    def on_fault(fault: ArgumentFault) -> Any:
        return wire.result(Refused(fault.message, hint=fault.hint, details={"argument": fault.argument}))

    server.add_middleware(ArgumentErrorMiddleware(on_fault))
    return server


async def _call(server: FastMCP, name: str, args: dict[str, Any]) -> Any:
    async with Client(server) as client:
        return await client.call_tool(name, args, raise_on_error=False)


async def test_a_typed_error_is_its_own_envelope_in_both_channels() -> None:
    res = await _call(_server(_wire()), "refuse", {"name": "x"})
    assert res.is_error
    envelope = res.structured_content["error"]
    assert envelope == {"kind": "input", "code": "refused", "message": "no x", "hint": "try another", "details": {"name": "x"}}
    assert res.content[0].text == 'no x\nHint: try another\nDetails: {"name":"x"}'


async def test_an_untyped_failure_is_a_defect_with_only_the_trace_id(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        res = await _call(_server(_wire()), "crash", {})
    envelope = res.structured_content["error"]
    assert envelope["kind"] == "bug"
    assert envelope["message"] == "internal error; trace_id=t-1"
    assert envelope["details"] == {"trace_id": "t-1"}
    assert "secret" not in res.content[0].text
    assert any("trace_id=t-1" in r.getMessage() and r.exc_info for r in caplog.records)


async def test_a_typed_bug_keeps_its_envelope_and_gains_the_trace_id(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        res = await _call(_server(_wire()), "typed_bug", {})
    envelope = res.structured_content["error"]
    assert envelope["message"] == "an invariant broke"
    assert envelope["details"] == {"where": "here", "trace_id": "t-1"}
    assert any("trace_id=t-1" in r.getMessage() for r in caplog.records)


async def test_an_argument_fault_reads_like_every_other_failure() -> None:
    res = await _call(_server(_wire()), "refuse", {"name": "x", "gone": 1})
    assert res.structured_content["error"]["details"] == {"argument": "gone"}
    assert res.content[0].text.startswith("refuse has no argument 'gone'")


async def test_a_dropped_param_is_absent_from_the_schema_and_the_call() -> None:
    server = _server(_wire())
    async with Client(server) as client:
        tools = {t.name: t for t in await client.list_tools()}
        ok = await client.call_tool("echo", {"name": "a"}, raise_on_error=False)
    assert "secret" not in tools["echo"].inputSchema["properties"]
    assert ok.structured_content == {"name": "a", "secret": ""}


async def test_passthrough_types_are_left_to_fastmcp() -> None:
    res = await _call(_server(_wire(passthrough=(ToolError,))), "shaped", {})
    assert res.is_error
    assert res.structured_content is None
    assert res.content[0].text == "already wire-shaped"
    caught = await _call(_server(_wire()), "shaped", {})
    assert caught.structured_content["error"]["kind"] == "bug"


async def test_the_text_renderer_and_logger_are_the_consumer_s(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("consumer.wire")
    wire = _wire(text=lambda error, envelope: f"{type(error).__name__}: {envelope['message']}", logger=logger)
    with caplog.at_level(logging.ERROR):
        refused = await _call(_server(wire), "refuse", {"name": "x"})
        await _call(_server(wire), "crash", {})
    assert refused.content[0].text == "Refused: no x"
    assert {r.name for r in caplog.records} == {"consumer.wire"}


def test_the_default_trace_id_is_fresh_per_failure() -> None:
    wire = ErrorWire(Defect)
    first = wire.result(RuntimeError("a")).structured_content
    second = wire.result(RuntimeError("b")).structured_content
    assert first is not None
    assert second is not None
    assert first["error"]["details"]["trace_id"] != second["error"]["details"]["trace_id"]


def test_long_details_are_cut_in_the_text_only() -> None:
    envelope = {"message": "m", "details": {"blob": "x" * (DETAILS_CHARS * 2)}}
    text = envelope_text(envelope)
    assert len(text) < DETAILS_CHARS + 100
    assert text.endswith("(cut; the structured error holds all of it)")
    assert envelope_text({"message": "m"}) == "m"


def test_typed_error_is_structural() -> None:
    assert isinstance(Refused("x"), TypedError)
    assert not isinstance(RuntimeError("x"), TypedError)
