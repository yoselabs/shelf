"""A local browser exchanges its token, while foreign browser authorities are refused."""

from __future__ import annotations

import pytest
from any_local_service import LocalService
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def app():
    async def home(request):
        return PlainTextResponse("private")

    return Starlette(routes=[Route("/", home), Route("/mcp/", home)])


def test_health_precedes_token_and_browser_exchange_removes_query():
    service = LocalService(app(), token="secret", version="1.0")
    with TestClient(service, base_url="http://127.0.0.1:8000") as client:
        assert client.get("/healthz").json()["version"] == "1.0"
        assert client.head("/healthz").content == b""
        assert client.get("/").status_code == 401
        assert client.get("/", headers={"X-Local-Token": "secret"}).text == "private"
        assert client.get("/?t=wrong").status_code == 401
        response = client.get("/?t=secret", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert client.get("/").text == "private"
        assert client.get("/", headers={"X-Local-Token": "wrong"}).status_code == 401


@pytest.mark.parametrize("path", ["/", "/healthz", "/mcp/"])
@pytest.mark.parametrize("headers", [{"host": "evil.example"}, {"origin": "http://evil.example"}, {"origin": "null"}])
def test_foreign_host_or_origin_is_refused_even_with_a_token(path, headers):
    with TestClient(LocalService(app(), token="secret"), base_url="http://localhost:8000") as client:
        assert client.get(path, headers={"X-Local-Token": "secret", **headers}).status_code == 403


def test_same_origin_and_websocket_refusal():
    with TestClient(LocalService(app(), token="secret"), base_url="http://localhost:8000") as client:
        assert client.get("/", headers={"origin": "http://localhost:8000", "X-Local-Token": "secret"}).status_code == 200
        with pytest.raises(WebSocketDisconnect), client.websocket_connect("/"):
            pytest.fail("a header-only service must refuse WebSockets")
