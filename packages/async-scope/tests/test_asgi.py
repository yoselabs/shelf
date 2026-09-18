"""Real sockets, a real uvicorn, a real client.

Every test here binds a loopback port and speaks HTTP over it. That is the point:
both behaviours this module exists for are invisible to a mock — one is a global
that another library sets behind uvicorn's back, the other is a shutdown that
hangs only when a real connection is still open. A fake server passes both while
broken.
"""

from __future__ import annotations

import asyncio
import socket
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from async_scope.asgi import LOOPBACK, ServeError, bind_loopback, serve_asgi

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

pytestmark = pytest.mark.net


async def _ok_app(scope: dict[str, Any], receive: Callable[[], Awaitable[Any]], send: Callable[[Any], Awaitable[None]]) -> None:
    """A minimal ASGI app that answers every request with 200 `pong`."""
    if scope["type"] == "lifespan":
        await _drain_lifespan(receive, send)
        return
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"pong"})


async def _never_finishing_app(
    scope: dict[str, Any], receive: Callable[[], Awaitable[Any]], send: Callable[[Any], Awaitable[None]]
) -> None:
    """Starts a response and then holds the connection open forever.

    The shape of a server-sent-event stream or a request blocked on a subprocess —
    which is what makes uvicorn's graceful drain never finish.
    """
    if scope["type"] == "lifespan":
        await _drain_lifespan(receive, send)
        return
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"opening", "more_body": True})
    await asyncio.sleep(3600)


async def _drain_lifespan(receive: Callable[[], Awaitable[Any]], send: Callable[[Any], Awaitable[None]]) -> None:
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


# --- bind_loopback ------------------------------------------------------


def test_bind_loopback_picks_a_free_port_and_reports_it() -> None:
    sock = bind_loopback()
    try:
        host, port = sock.getsockname()
        assert host == LOOPBACK
        assert port > 0
    finally:
        sock.close()


def test_bind_loopback_picks_a_different_port_each_time() -> None:
    """Why `port=0` instead of a constant: two of these must be able to coexist."""
    first = bind_loopback()
    second = bind_loopback()
    try:
        assert first.getsockname()[1] != second.getsockname()[1]
    finally:
        first.close()
        second.close()


def test_bind_loopback_raises_serve_error_on_a_taken_port() -> None:
    held = bind_loopback()
    try:
        taken = int(held.getsockname()[1])
        with pytest.raises(ServeError, match="cannot bind TCP"):
            bind_loopback(port=taken)
    finally:
        held.close()


def test_bind_loopback_closes_the_socket_when_the_bind_fails() -> None:
    """A failed bind must not leak the descriptor it opened to try."""
    with pytest.raises(ServeError):
        bind_loopback(host="203.0.113.1")  # TEST-NET-3: not on any local interface


# --- serve_asgi ---------------------------------------------------------


async def test_serve_asgi_answers_a_real_request() -> None:
    async with serve_asgi(_ok_app) as url:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/ping")
        assert response.status_code == 200
        assert response.text == "pong"


async def test_serve_asgi_yields_a_base_url_with_no_path_and_no_trailing_slash() -> None:
    async with serve_asgi(_ok_app) as url:
        assert url.startswith(f"http://{LOOPBACK}:")
        assert not url.endswith("/")
        assert int(url.rsplit(":", 1)[1]) > 0


async def test_serve_asgi_releases_the_port_on_exit() -> None:
    async with serve_asgi(_ok_app) as url:
        port = int(url.rsplit(":", 1)[1])

    reclaimed = bind_loopback(port=port)
    reclaimed.close()


async def test_a_failed_startup_raises_instead_of_exiting_the_process() -> None:
    """uvicorn reports a failed lifespan as `SystemExit`, because it is written to
    be a program. Inside someone else's process that is a request to exit, and
    `BaseException` means no ordinary `except` between here and the top will stop
    it — one bad app would end the whole run instead of this one serve."""

    async def exploding_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        msg = "lifespan refused"
        raise RuntimeError(msg)

    with pytest.raises(ServeError, match="exited during startup"):
        async with serve_asgi(exploding_app, startup_timeout=5.0):
            pass


async def test_a_server_that_never_starts_gives_up_instead_of_spinning() -> None:
    async def silent_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        await asyncio.sleep(3600)  # never completes lifespan startup

    with pytest.raises(ServeError, match="did not start within"):
        async with serve_asgi(silent_app, startup_timeout=0.5):
            pass


# --- the two lessons ----------------------------------------------------


async def test_a_second_serve_is_not_poisoned_by_the_first() -> None:
    """sse-starlette copies uvicorn's `should_exit` into a module-global and never
    resets it, so the flag that stopped serve #1 is still set when serve #2 starts
    and aborts its first streaming response. Poison it by hand and serve again."""
    from sse_starlette.sse import AppStatus  # noqa: PLC0415

    AppStatus.should_exit = True

    async with serve_asgi(_ok_app) as url:
        assert not AppStatus.should_exit
        async with httpx.AsyncClient() as client:
            assert (await client.get(f"{url}/ping")).text == "pong"


async def test_two_serves_in_one_process_both_answer() -> None:
    """The end-to-end shape of the same bug: serial serves, as a suite does."""
    for _ in range(2):
        async with serve_asgi(_ok_app) as url, httpx.AsyncClient() as client:
            assert (await client.get(f"{url}/ping")).status_code == 200


async def test_teardown_does_not_wait_for_a_stream_that_never_ends() -> None:
    """A graceful shutdown drains open connections; this connection never drains.

    On uvicorn 0.51 `force_exit` does not rescue this on its own — `serve()` simply
    does not return — so what is being checked is that the grace expires and the
    cancel finishes the job, rather than the caller paying an open-ended wait.
    """
    loop = asyncio.get_running_loop()

    async with serve_asgi(_never_finishing_app, shutdown_grace=1.0) as url:
        client = httpx.AsyncClient(timeout=30.0)
        request = client.build_request("GET", f"{url}/stream")
        response = await client.send(request, stream=True)
        assert response.status_code == 200
        # Deliberately NOT closed: an open connection is the precondition.
        entered = loop.time()

    # The grace expires (uvicorn will not return here) and the cancel takes over
    # immediately, so teardown costs the grace and not a second more.
    assert loop.time() - entered < 2.0
    await client.aclose()


async def test_the_port_is_free_even_after_a_stream_held_it_open() -> None:
    """The leak the graceful drain causes is a LISTEN socket nothing ever closes."""
    async with serve_asgi(_never_finishing_app) as url:
        port = int(url.rsplit(":", 1)[1])
        client = httpx.AsyncClient(timeout=30.0)
        await client.send(client.build_request("GET", f"{url}/stream"), stream=True)

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind((LOOPBACK, port))
    finally:
        probe.close()
        await client.aclose()
