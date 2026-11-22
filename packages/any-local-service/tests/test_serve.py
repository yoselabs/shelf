"""A real local server publishes discovery only while bound and closes its lifespan."""

from __future__ import annotations

import contextlib

import httpx
import pytest
from any_local_service import LocalService
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route


@pytest.mark.net
@pytest.mark.asyncio
async def test_endpoint_and_lifespan_follow_the_server_lifetime(tmp_path, caplog, capfd):
    stopped = []

    @contextlib.asynccontextmanager
    async def lifespan(app):
        yield
        stopped.append(True)

    async def home(request):
        return PlainTextResponse("hello")

    service = LocalService(Starlette(routes=[Route("/", home)], lifespan=lifespan), token="secret")
    endpoint = tmp_path / "endpoint.url"
    async with service.serving(endpoint=endpoint) as url:
        assert endpoint.read_text() == url
        async with httpx.AsyncClient(trust_env=False) as client:
            assert (await client.get(f"{url}/healthz")).status_code == 200
            assert (await client.get(url, headers={"X-Local-Token": "secret"})).text == "hello"
    assert stopped == [True]
    assert not endpoint.exists()
    logs = caplog.text + capfd.readouterr().err
    assert "CancelledError" not in logs
    assert "ClosedResourceError" not in logs


@pytest.mark.net
@pytest.mark.asyncio
async def test_body_failure_still_unpublishes_endpoint(tmp_path):
    endpoint = tmp_path / "endpoint.url"
    with pytest.raises(RuntimeError, match="consumer failed"):
        async with LocalService(Starlette(), token="secret").serving(endpoint=endpoint):
            message = "consumer failed"
            raise RuntimeError(message)
    assert not endpoint.exists()


@pytest.mark.parametrize("port", [-1, 65536])
def test_bad_port_refused_before_server_start(port):
    with pytest.raises(ValueError, match="port"):
        LocalService(Starlette(), token="secret").run(port=port)
