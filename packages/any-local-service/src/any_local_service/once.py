"""An HTTP transport may answer once, even when its session closes after replying."""

from __future__ import annotations

from typing import TYPE_CHECKING

from anyio import ClosedResourceError

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send


class ResponseOnceMiddleware:
    """Drop a second response and a closed-stream error only after a completed reply."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        started = completed = dropping = False

        async def once(message: Message) -> None:
            nonlocal started, completed, dropping
            if message["type"] == "http.response.start":
                if started:
                    dropping = True
                    return
                started = True
            if dropping:
                return
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                completed = True

        try:
            await self._app(scope, receive, once)
        except ClosedResourceError:
            if not completed:
                raise
