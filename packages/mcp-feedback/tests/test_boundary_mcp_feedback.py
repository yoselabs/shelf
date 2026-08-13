"""Load-bearing invariants: no consumer import, no OTel SDK dependency,
delivery failure never raises to the caller.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import httpx
import mcp_feedback
import pytest
from fastmcp import Client, FastMCP
from mcp_feedback import register_feedback_tool

_CONSUMERS = {"a2web", "a2kay", "a2kit"}


def test_imports_no_consumer() -> None:
    pkg_dir = Path(mcp_feedback.__file__).parent
    offenders: list[str] = []
    for py in pkg_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [f"{py.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in _CONSUMERS]
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _CONSUMERS:
                offenders.append(f"{py.name}: from {node.module}")
    assert offenders == [], f"mcp_feedback must not import a consumer: {offenders}"


def test_no_opentelemetry_sdk_dependency() -> None:
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())
    deps = " ".join(data["project"]["dependencies"])
    assert "opentelemetry" not in deps.lower()


_CONNECTION_REFUSED = "connection refused"


class _FailingTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(_CONNECTION_REFUSED)


@pytest.mark.asyncio
async def test_delivery_failure_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    real_client_cls = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client_cls(**kw, transport=_FailingTransport()))
    server = FastMCP("t")
    register_feedback_tool(server, endpoint="https://gateway.test/logs", api_key="k")

    async with Client(server) as client:
        res = await client.call_tool("report_feedback", {"subject": "s", "note": "n"})

    # attempted — delivery failure is swallowed, not surfaced as sent=False or a raised error
    assert res.structured_content["sent"] is True
