"""Call a tool on a Streamable HTTP MCP server with httpx alone.

A process that starts, makes one call and exits (a CLI beside a running server, a job reaching
back to its host) pays for its imports every time. The MCP SDK and fastmcp cost about a second
to import; httpx about a tenth of that. This speaks the client half of Streamable HTTP that such
a call needs: ``initialize``, ``notifications/initialized``, ``tools/list``, ``tools/call``,
with the session header when the server issues one. A reply may be a JSON body or a short SSE
stream; both are read.

    with McpEndpoint("http://127.0.0.1:8765/mcp/", headers={"X-Token": token}) as server:
        print(server.server.version)
        result = server.call("search", {"query": "pier"})
        if result.is_error: ...

A refused connection is :class:`EndpointRefused`, so a caller can tell "nothing listens there"
from a server that answered badly (:class:`McpCallError`). A tool's own failure is a result with
``is_error`` set, never an exception: that is the protocol's own split.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self

import httpx

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import TracebackType

#: The protocol version this client asks for; the server's answer is the one used after.
PROTOCOL_VERSION = "2025-06-18"
_SESSION_HEADER = "mcp-session-id"
_VERSION_HEADER = "mcp-protocol-version"


class McpCallError(RuntimeError):
    """The server answered, but not with what the protocol promises (a JSON-RPC error, an
    HTTP error status, or a reply with no message for the request)."""

    def __init__(self, message: str, *, status: int | None = None, code: int | None = None, data: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.data = data


class EndpointRefused(McpCallError):  # noqa: N818 — names the situation a caller branches on
    """Nothing accepted the connection at the endpoint's address."""


@dataclass(frozen=True)
class ServerInfo:
    """What the server said about itself in ``initialize``."""

    name: str
    version: str | None
    protocol_version: str
    instructions: str | None = None


@dataclass(frozen=True)
class ToolResult:
    """A ``tools/call`` result: its content blocks, its structured content, and whether the
    tool reported a failure."""

    content: list[dict[str, Any]] = field(default_factory=list)
    structured: dict[str, Any] | None = None
    is_error: bool = False

    @property
    def text(self) -> str:
        """The text blocks, joined: what a client that renders text would show."""
        return "".join(str(block.get("text", "")) for block in self.content if block.get("type") == "text")


class McpEndpoint:
    """One session with one MCP server over Streamable HTTP. Use it as a context manager:
    entering initializes the session, leaving ends it."""

    def __init__(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 30.0,
        client_name: str = "mcp-call",
        client_version: str = "0",
    ) -> None:
        self.url = url
        self._headers = dict(headers or {})
        self._timeout = timeout
        self._client_info = {"name": client_name, "version": client_version}
        self._http: httpx.Client | None = None
        self._session: str | None = None
        self._ids = itertools.count(1)
        self._server: ServerInfo | None = None

    @property
    def server(self) -> ServerInfo:
        """The server's ``initialize`` answer; available once the session is open."""
        if self._server is None:
            msg = "the session is not open: use the endpoint as a context manager first"
            raise McpCallError(msg)
        return self._server

    def __enter__(self) -> Self:
        # A server may move the endpoint (`/mcp/` to `/mcp`) with a 307, which keeps the method and body.
        self._http = httpx.Client(timeout=self._timeout, follow_redirects=True)
        try:
            result = self._request("initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": self._client_info})
            info = result.get("serverInfo") or {}
            self._server = ServerInfo(
                name=str(info.get("name", "")),
                version=info.get("version"),
                protocol_version=str(result.get("protocolVersion", PROTOCOL_VERSION)),
                instructions=result.get("instructions"),
            )
            self._notify("notifications/initialized")
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()

    def close(self) -> None:
        """End the session (best effort: a server may not support ending one) and the connection."""
        if self._http is None:
            return
        try:
            if self._session is not None:
                self._http.delete(self.url, headers=self._send_headers())
        except httpx.HTTPError:
            pass
        finally:
            self._http.close()
            self._http = None

    def tools(self) -> list[dict[str, Any]]:
        """Every tool the server lists, as the protocol describes them (name, inputSchema, ...)."""
        found: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = self._request("tools/list", {"cursor": cursor} if cursor else {})
            found += page.get("tools", [])
            cursor = page.get("nextCursor")
            if not cursor:
                return found

    def call(self, tool: str, arguments: Mapping[str, Any] | None = None, *, timeout: float | None = None) -> ToolResult:
        """Call ``tool``. A failure the tool reports comes back with ``is_error`` set."""
        result = self._request("tools/call", {"name": tool, "arguments": dict(arguments or {})}, timeout=timeout)
        return ToolResult(
            content=list(result.get("content", [])),
            structured=result.get("structuredContent"),
            is_error=bool(result.get("isError", False)),
        )

    # --- the wire -------------------------------------------------------------------

    def _send_headers(self) -> dict[str, str]:
        headers = {"accept": "application/json, text/event-stream", "content-type": "application/json", **self._headers}
        if self._session is not None:
            headers[_SESSION_HEADER] = self._session
        if self._server is not None:
            headers[_VERSION_HEADER] = self._server.protocol_version
        return headers

    def _post(self, message: dict[str, Any], timeout: float | None) -> httpx.Response:
        if self._http is None:
            msg = "the session is not open: use the endpoint as a context manager first"
            raise McpCallError(msg)
        try:
            response = self._http.post(
                self.url, content=json.dumps(message), headers=self._send_headers(), timeout=timeout or self._timeout
            )
        except httpx.ConnectError as exc:
            msg = f"nothing accepted the connection at {self.url}"
            raise EndpointRefused(msg) from exc
        except httpx.HTTPError as exc:
            msg = f"the request to {self.url} failed: {exc}"
            raise McpCallError(msg) from exc
        if response.is_error:
            msg = f"{self.url} answered HTTP {response.status_code}: {response.text[:300]}"
            raise McpCallError(msg, status=response.status_code)
        if self._session is None and _SESSION_HEADER in response.headers:
            self._session = response.headers[_SESSION_HEADER]
        return response

    def _notify(self, method: str) -> None:
        self._post({"jsonrpc": "2.0", "method": method}, None)

    def _request(self, method: str, params: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        request_id = next(self._ids)
        response = self._post({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}, timeout)
        for message in _messages(response):
            if message.get("id") != request_id:
                continue  # a server notification or request on the stream: not this reply
            if "error" in message:
                error = message["error"] or {}
                msg = f"{method}: {error.get('message', 'error')}"
                raise McpCallError(msg, status=response.status_code, code=error.get("code"), data=error.get("data"))
            return message.get("result") or {}
        msg = f"{method}: the server's reply held no answer to request {request_id}"
        raise McpCallError(msg, status=response.status_code)


def _messages(response: httpx.Response) -> list[dict[str, Any]]:
    """The JSON-RPC messages in a reply: one JSON body, or every ``data:`` event of an SSE stream."""
    kind = response.headers.get("content-type", "").split(";")[0].strip()
    if kind == "text/event-stream":
        found: list[dict[str, Any]] = []
        data: list[str] = []
        for line in [*response.text.splitlines(), ""]:
            if line.startswith("data:"):
                data.append(line[5:].removeprefix(" "))
            elif line == "" and data:
                found.append(json.loads("\n".join(data)))
                data = []
        return found
    if not response.content:
        return []
    body = response.json()
    return body if isinstance(body, list) else [body]


__all__ = ["PROTOCOL_VERSION", "EndpointRefused", "McpCallError", "McpEndpoint", "ServerInfo", "ToolResult"]
