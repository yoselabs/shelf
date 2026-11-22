"""Exchange a browser navigation token for a cookie before the existing header gate."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, cast

from asgi_token_gate import StaticTokenGate
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


class BrowserTokenGate:
    """Root ``?t=`` navigation becomes an HttpOnly, SameSite=strict session cookie."""

    def __init__(self, app: ASGIApp, token: str, *, header: str = "X-Local-Token", cookie: str = "local_session") -> None:
        self._app = cast("ASGIApp", StaticTokenGate(app, token, header=header))
        self._token = token.encode()
        self._header = header.lower()
        self._cookie = cookie

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] == "http":
            request = Request(scope)
            if scope["path"] == "/" and "t" in request.query_params:
                await self._exchange(request, scope, receive, send)
                return
            cookie = request.cookies.get(self._cookie)
            credential = request.headers.get(self._header, cookie or "")
            if not credential.isascii():
                await JSONResponse({"error": "invalid token"}, status_code=401)(scope, receive, send)
                return
            if cookie and self._header not in request.headers:
                scope = {**scope, "headers": [*scope["headers"], (self._header.encode(), cookie.encode())]}
        await self._app(scope, receive, send)

    async def _exchange(self, request: Request, scope: Scope, receive: Receive, send: Send) -> None:
        if secrets.compare_digest(request.query_params["t"].encode(), self._token):
            response = RedirectResponse("/", status_code=303)
            response.set_cookie(self._cookie, self._token.decode(), httponly=True, samesite="strict", path="/")
        else:
            response = JSONResponse({"error": "invalid token"}, status_code=401)
        response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        await response(scope, receive, send)
