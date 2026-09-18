"""Serve an ASGI app on a loopback port for the body of an ``async with``.

Separate from the package root because it needs a server — install
``async-scope[asgi]`` for uvicorn — while the root stays dependency-free.

It belongs in this package rather than beside it because everything it knows is a
way a scope fails to close cleanly, which is what the rest of the package is
about.

* A shutdown flag copied into another library's process-global that nothing ever
  resets, so the *next* server in the process is born broken.
* A graceful shutdown that waits for a response which never ends, so teardown
  hangs with no traceback and the listening socket stays held.
* A failed startup that arrives as ``SystemExit`` rather than an exception, which
  asyncio re-raises into the event loop — so the caller's ``except`` never runs,
  the loop unwinds, and the real cause is only in the log.

None of the three is a misuse of uvicorn. Every one of them was paid for.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import sys
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

LOOPBACK = "127.0.0.1"


class ServeError(RuntimeError):
    """A socket could not be bound, or a server failed to start."""


def bind_loopback(host: str = LOOPBACK, port: int = 0, *, backlog: int = 16) -> socket.socket:
    """Bind a listening TCP socket on ``host``; ``port=0`` picks a free one.

    The caller owns the socket and closes it. Read the chosen port back with
    ``sock.getsockname()[1]`` — which is the whole point of passing ``0``: asking
    the kernel beats picking a number and hoping, and beats retrying on
    ``EADDRINUSE`` in a loop, which is what a fixed port turns into as soon as two
    tests run at once.

    ``SO_REUSEADDR`` is set so a socket still in ``TIME_WAIT`` from the previous
    run does not refuse the bind.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError as exc:
        sock.close()
        msg = f"cannot bind TCP at {host}:{port}: {exc}"
        raise ServeError(msg) from exc
    sock.listen(backlog)
    return sock


@contextlib.asynccontextmanager
async def serve_asgi(
    app: Any,
    *,
    host: str = LOOPBACK,
    port: int = 0,
    startup_timeout: float = 10.0,
    shutdown_grace: float = 2.0,
    log_level: str = "warning",
) -> AsyncIterator[str]:
    """Serve ``app`` on ``host:port`` for the body, yielding its base URL.

    Yields ``http://host:port`` with no trailing slash and no path — append your
    own. Does not yield until the server reports started, so the body never races
    the bind; a server that fails to start raises that failure rather than the
    timeout, and a server that neither starts nor fails raises
    :class:`ServeError` after ``startup_timeout``.

    On the way out the server is stopped and the socket closed, whatever the body
    did. ``shutdown_grace`` is how long a clean exit is given before the serve task
    is cancelled outright; see :func:`_stop` for why that cancel is not optional.
    """
    import uvicorn  # noqa: PLC0415 — heavy, and only the serve path pays for it

    _reset_sse_starlette_shutdown_flag()

    sock = bind_loopback(host, port)
    bound_port = int(cast("tuple[Any, ...]", sock.getsockname())[1])
    server = uvicorn.Server(uvicorn.Config(app, log_level=log_level, lifespan="on"))
    task = asyncio.create_task(_serve_without_exiting(server, sock))
    try:
        await _await_started(server, task, within=startup_timeout)
        yield f"http://{host}:{bound_port}"
    finally:
        await _stop(server, task, grace=shutdown_grace)
        with contextlib.suppress(Exception):
            sock.close()


async def _serve_without_exiting(server: Any, sock: socket.socket) -> None:
    """Run ``server.serve`` with its ``SystemExit`` converted before asyncio sees it.

    uvicorn is written to be a program: an app that raises during lifespan startup
    ends in ``sys.exit(3)``, not an exception. That distinction is not cosmetic
    inside someone else's event loop. ``Task`` special-cases ``SystemExit`` and
    ``KeyboardInterrupt`` — it stores them AND re-raises them into the loop, which
    stops the loop and cancels whatever was awaiting. So a caller who wraps the
    serve in ``try/except`` does not get the startup error; it gets a
    ``CancelledError`` from its own runner, after the loop has already begun
    unwinding, and the actual cause is only in the log. Converting here, inside the
    task, is the only place early enough to matter.
    """
    try:
        await server.serve(sockets=[sock])
    except SystemExit as exc:
        msg = f"the server exited during startup (status {exc.code})"
        raise ServeError(msg) from exc


def _reset_sse_starlette_shutdown_flag() -> None:
    """Clear sse-starlette's PROCESS-GLOBAL shutdown flag before a serve.

    sse-starlette monkey-patches uvicorn and runs a watcher that copies the
    server's ``should_exit`` into its module-global ``AppStatus.should_exit`` —
    and never resets it. So the flag that stopped the *previous* server is still
    set when the next one starts, and it aborts that server's first SSE response
    with "ASGI callable returned without completing response". Serial serves in
    one process — a test suite, a restarted daemon — break, and the failure
    points at the innocent second server.

    Reached through ``sys.modules`` rather than an import, and that is the accurate
    spelling of the relationship: sse-starlette is not a dependency of this package
    and must not become one. If nothing has imported it, there is no global to
    poison and nothing to do — importing it here to reset a flag nobody set would
    be work, and a dependency, in exchange for nothing.

    Suppressed wholesale beyond that: this is a workaround for somebody else's bug,
    and a serve must not fail because that library moved its internals.
    """
    module = sys.modules.get("sse_starlette.sse")
    if module is None:
        return
    with contextlib.suppress(Exception):
        module.AppStatus.should_exit = False


async def _await_started(server: Any, task: asyncio.Task[Any], *, within: float) -> None:
    """Block until the server reports started, or surface why it never will.

    Not yielding before ``started`` is what keeps the body from racing the bind.

    A failed startup surfaces as whatever :func:`_serve_without_exiting` turned it
    into, rather than as this function's timeout.
    """
    deadline = asyncio.get_running_loop().time() + within
    while not server.started:
        if task.done():
            task.result()  # a startup failure belongs to the caller, not the timeout
            msg = "the server exited during startup"
            raise ServeError(msg)
        if asyncio.get_running_loop().time() >= deadline:
            msg = f"the server did not start within {within}s"
            raise ServeError(msg)
        await asyncio.sleep(0.02)


async def _stop(server: Any, task: asyncio.Task[Any], *, grace: float) -> None:
    """Stop the server without waiting for a response that may never end.

    ``should_exit`` alone asks uvicorn for a GRACEFUL shutdown, which waits for
    open connections to drain. A long-lived response — server-sent events, a
    Streamable-HTTP stream, a request blocked on a subprocess — never drains, so
    the shutdown, and the ``await`` behind it, hang with no traceback while the
    listening socket stays held.

    ``force_exit`` is documented to skip that drain and it is set here, but on
    uvicorn 0.51 it is **not sufficient on its own**: measured against a handler
    holding an open response, `serve()` does not return at all, and a caller that
    only waits ends up paying its entire timeout on every teardown. So the wait is
    a short grace for the ordinary case — measured at ~0.15s when nothing is stuck
    — after which the task is cancelled outright. The shield matters: it lets the
    grace expire without the wait cancelling the task first, so the cancel is this
    function's own deliberate step rather than a timeout's side effect.
    """
    server.should_exit = True
    server.force_exit = True
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=grace)
    except Exception:  # noqa: BLE001 — TimeoutError is the expected one; anything else still has to reach the cancel
        task.cancel()
        with contextlib.suppress(BaseException):
            await task


__all__ = ["LOOPBACK", "ServeError", "bind_loopback", "serve_asgi"]
