"""Loopback serving delegates socket and async shutdown ownership to async-scope."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import uvicorn
from async_scope.asgi import bind_loopback, serve_asgi

from any_local_service.endpoint import published_endpoint
from any_local_service.logs import teardown_logs

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable
    from pathlib import Path

    from starlette.types import ASGIApp


def validate_port(port: int) -> None:
    """Refuse a port outside the TCP range before allocating a socket."""
    if not 0 <= port <= 65535:
        message = "port must be between 0 and 65535"
        raise ValueError(message)


@contextlib.asynccontextmanager
async def serving(app: ASGIApp, *, port: int = 0, endpoint: Path | None = None) -> AsyncGenerator[str]:
    """Yield the bound URL; stop the service after unpublishing discovery."""
    validate_port(port)
    with teardown_logs():
        async with serve_asgi(app, port=port) as url:
            with contextlib.ExitStack() as publication:
                if endpoint is not None:
                    publication.enter_context(published_endpoint(endpoint, url))
                yield url


def run(app: ASGIApp, *, port: int = 0, on_bound: Callable[[str], None] | None = None) -> None:
    """Run until a signal; uvicorn owns signals and graceful lifespan shutdown."""
    validate_port(port)
    with teardown_logs(), bind_loopback(port=port) as sock:
        if on_bound is not None:
            on_bound(f"http://127.0.0.1:{sock.getsockname()[1]}")
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="on", access_log=False, timeout_graceful_shutdown=2))
        server.run(sockets=[sock])
