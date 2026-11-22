"""A loopback browser authority boundary, including unauthenticated health requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


class LoopbackBoundary:
    """Refuse a foreign Host or Origin before any inner HTTP route can run."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            request = Request(scope)
            server = scope.get("server")
            port = server[1] if server else None
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if port == 80:
                hosts |= {"127.0.0.1", "localhost"}
            host = request.headers.get("host", "")
            origin = request.headers.get("origin")
            if host not in hosts or (origin is not None and origin != f"http://{host}"):
                await JSONResponse({"error": "Host or Origin refused"}, status_code=403)(scope, receive, send)
                return
        await self._app(scope, receive, send)
