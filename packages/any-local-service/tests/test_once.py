"""A late transport failure never sends a second reply or hides an unfinished one."""

from __future__ import annotations

import httpx
import pytest
from any_local_service.once import ResponseOnceMiddleware
from anyio import ClosedResourceError


@pytest.mark.asyncio
async def test_completed_response_survives_late_second_response_and_stream_close():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 202, "headers": []})
        await send({"type": "http.response.body", "body": b"accepted"})
        await send({"type": "http.response.start", "status": 500, "headers": []})
        await send({"type": "http.response.body", "body": b"late failure"})
        raise ClosedResourceError

    async with httpx.AsyncClient(transport=httpx.ASGITransport(ResponseOnceMiddleware(app)), base_url="http://local") as client:
        response = await client.post("/")
        assert response.status_code == 202
        assert response.text == "accepted"


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ClosedResourceError, ValueError])
async def test_early_or_unrelated_failure_is_not_hidden(error):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"partial", "more_body": True})
        raise error

    async with httpx.AsyncClient(transport=httpx.ASGITransport(ResponseOnceMiddleware(app)), base_url="http://local") as client:
        with pytest.raises(error):
            await client.get("/")
