"""mcp-bridge — a stdio MCP server that relays to a Streamable HTTP one.

A client that can only start a local program (Claude Desktop's Chat tab) cannot reach an MCP
server over HTTP. :func:`build_bridge` is that program's server: every request it receives on
stdio goes to ``url``, so the client sees the remote server's own tools.

It wraps FastMCP's proxy and adds what a long-running relay needs:

- **Headers per request.** ``headers`` is a mapping, or a function called for each request, so a
  consumer can send a token and name the caller (see :func:`downstream_client_name`).
- **A fresh server session per call** (FastMCP's proxy does this). A server restart therefore never
  strands the client: the next call opens a new session.
- **Waiting out a restart.** A call made while the server refuses connections is retried for up
  to ``wait`` seconds, then sent. Only a refused connection waits: a refused token or any other
  failure returns at once.
"""

from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING, Any, Self, override

import httpx
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server.providers.proxy import FastMCPProxy, ProxyClient

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

#: How long a call waits for a server that refuses connections: long enough for a restart.
DEFAULT_WAIT = 60.0
_RETRY = 0.5


def build_bridge(
    url: str,
    *,
    headers: Mapping[str, str] | Callable[[], Mapping[str, str]] | None = None,
    wait: float = DEFAULT_WAIT,
    name: str = "bridge",
) -> FastMCPProxy:
    """A FastMCP server relaying every request to ``url``; ``.run(transport="stdio")`` serves it."""

    def client() -> ProxyClient[Any]:
        sent = dict(headers() if callable(headers) else headers or {})
        return _waiting_client()(StreamableHttpTransport(url, headers=sent), wait=wait)

    return FastMCPProxy(client_factory=client, name=name)


def downstream_client_name() -> str | None:
    """The name the stdio client gave in its ``initialize``, inside a relayed request."""
    from fastmcp.server.dependencies import get_context  # noqa: PLC0415 — only a request has a context

    try:
        params = get_context().session.client_params
    except (RuntimeError, AttributeError):
        return None
    return params.clientInfo.name if params is not None and params.clientInfo.name else None


def refused(exc: BaseException) -> bool:
    """Whether ``exc`` is, or was caused by, a refused connection: the server is down."""
    found: BaseException | None = exc
    while found is not None:
        if isinstance(found, httpx.ConnectError):
            return True
        found = found.__cause__ or found.__context__
    return False


@functools.cache
def _waiting_client() -> type[ProxyClient[Any]]:
    # The base stays unsubscripted: a `ProxyClient[...]` base breaks the proxy's per-request
    # copy of the client (every call failed "Invalid request parameters").
    class WaitingClient(ProxyClient):  # pyrefly: ignore[implicit-any-type-argument]
        """A proxy client whose connect waits out a server that is restarting."""

        def __init__(self, transport: Any, *, wait: float) -> None:
            super().__init__(transport)
            self._wait = wait

        @override
        async def __aenter__(self) -> Self:
            deadline = asyncio.get_running_loop().time() + self._wait
            while True:
                try:
                    await super().__aenter__()
                except Exception as exc:
                    if not refused(exc) or asyncio.get_running_loop().time() >= deadline:
                        raise
                    await asyncio.sleep(_RETRY)
                else:
                    return self

    return WaitingClient


__all__ = ["DEFAULT_WAIT", "build_bridge", "downstream_client_name", "refused"]
