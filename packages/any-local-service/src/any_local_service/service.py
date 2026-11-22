"""The local service a consumer holds, with one safe composition by default."""

from __future__ import annotations

from typing import TYPE_CHECKING

from any_local_service import serve
from any_local_service.access import BrowserTokenGate
from any_local_service.boundary import LoopbackBoundary
from any_local_service.health import HealthEndpoint
from any_local_service.once import ResponseOnceMiddleware
from any_local_service.readiness import Readiness

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager
    from pathlib import Path

    from starlette.types import ASGIApp, Receive, Scope, Send


class LocalService:
    """Own a guarded ASGI service; health is public only behind the authority boundary."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        token: str,
        version: str = "0.1.0",
        header: str = "X-Local-Token",
        cookie: str = "local_session",
        readiness: Readiness | None = None,
    ) -> None:
        self.readiness = readiness if readiness is not None else Readiness()
        if readiness is None:
            self.readiness.ready()
        self.app = LoopbackBoundary(
            HealthEndpoint(
                BrowserTokenGate(ResponseOnceMiddleware(app), token, header=header, cookie=cookie), self.readiness, version=version
            )
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)

    def serving(self, *, port: int = 0, endpoint: Path | None = None) -> AbstractAsyncContextManager[str]:
        """Serve for the body, yielding the bound URL and publishing it when requested."""
        return serve.serving(self, port=port, endpoint=endpoint)

    def run(self, *, port: int = 0, on_bound: Callable[[str], None] | None = None) -> None:
        """Run the service on IPv4 loopback until uvicorn receives a stop signal."""
        serve.run(self, port=port, on_bound=on_bound)
