"""Public health before authentication, including a boot that publishes its app later."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, TypeAlias

from async_scope import ResourceScope
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.types import ASGIApp, Receive, Scope, Send

    from any_local_service.readiness import Readiness

Boot: TypeAlias = "Callable[[Callable[[ASGIApp], None]], Awaitable[None]]"
HEALTHZ_PATH = "/healthz"


def healthz_body(
    readiness: Readiness, version: str, details: Callable[[], dict[str, object]] | None = None
) -> tuple[int, dict[str, object]]:
    """Return status plus the complete readiness stage and build identity."""
    stage = readiness.current()
    ready = stage.name == "ready"
    return (200 if ready else 503), {**(details() if details else {}), "ready": ready, **stage.to_json(), "version": version}


async def _answer(
    readiness: Readiness,
    version: str,
    scope: Scope,
    receive: Receive,
    send: Send,
    *,
    details: Callable[[], dict[str, object]] | None = None,
) -> None:
    status, body = healthz_body(readiness, version, details)
    headers = {"Retry-After": "1"} if status == 503 else {}
    response = JSONResponse(body, status_code=status, headers=headers)
    if scope["method"] == "HEAD":
        response.body = b""
    await response(scope, receive, send)


class HealthEndpoint:
    """Answer GET/HEAD health outside the token gate; delegate everything else."""

    def __init__(self, app: ASGIApp, readiness: Readiness, *, version: str) -> None:
        self._app, self._readiness, self._version = app, readiness, version

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] == HEALTHZ_PATH and scope["method"] in {"GET", "HEAD"}:
            await _answer(self._readiness, self._version, scope, receive, send)
            return
        await self._app(scope, receive, send)


class ReadinessGate:
    """Serve health during boot, then delegate to the published app; own the boot task."""

    def __init__(
        self,
        readiness: Readiness,
        boot: Boot,
        *,
        version: str,
        on_failure: Callable[[BaseException], None],
        details: Callable[[], dict[str, object]] | None = None,
    ) -> None:
        self._readiness, self._boot, self._version, self._on_failure = readiness, boot, version, on_failure
        self._details = details
        self._app: ASGIApp | None = None
        self.failure: BaseException | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._lifespan(receive, send)
        elif scope["type"] == "http" and scope["path"] == HEALTHZ_PATH and scope["method"] in {"GET", "HEAD"}:
            await _answer(self._readiness, self._version, scope, receive, send, details=self._details)
        elif self._app is not None and self.failure is None:
            await self._app(scope, receive, send)
        elif scope["type"] == "http":
            await _answer(self._readiness, self._version, scope, receive, send, details=self._details)
        else:
            await send({"type": "websocket.close", "code": 1013})

    def _publish(self, app: ASGIApp) -> None:
        self._app = app

    async def _run_boot(self) -> None:
        try:
            await self._boot(self._publish)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.failure = exc
            self._readiness.refuse(str(exc) or type(exc).__name__)
            self._on_failure(exc)

    async def _lifespan(self, receive: Receive, send: Send) -> None:
        async with ResourceScope() as resources:
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    resources.spawn(self._run_boot())
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await resources.aclose()
                    self._app = None
                    await send({"type": "lifespan.shutdown.complete"})
                    return
