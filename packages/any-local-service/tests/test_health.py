"""A client sees boot progress before authentication and app publication."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from any_local_service import LocalService
from any_local_service.health import ReadinessGate
from any_local_service.readiness import Readiness, Stage
from starlette.applications import Starlette
from starlette.testclient import TestClient


def test_health_reports_stages_progress_blockers_and_refusal():
    readiness = Readiness()
    events = []
    unsubscribe = readiness.subscribe(lambda event, stage: events.append(event))
    with TestClient(LocalService(Starlette(), token="secret", readiness=readiness), base_url="http://localhost:8000") as client:
        assert client.get("/healthz").json()["stage"] == "starting"
        with readiness.stage("opening", "opening the store"):
            readiness.progress(2, 5)
            response = client.get("/healthz")
            assert response.status_code == 503
            assert response.headers["retry-after"] == "1"
            assert response.json()["progress"] == {"done": 2, "total": 5}
        readiness.ready()
        assert client.get("/healthz").status_code == 200
        remove = readiness.add_blocker(lambda: Stage("locked", "operator action needed", files=("one",)))
        assert client.get("/healthz").json()["files"] == ["one"]
        remove()
        assert client.get("/healthz").status_code == 200
        readiness.refuse("cannot open")
        assert client.get("/healthz").json()["stage"] == "refused"
    unsubscribe()
    assert events == ["start", "progress", "end", "ready", "refused"]


@pytest.mark.net
@pytest.mark.asyncio
async def test_boot_publication_and_shutdown_are_owned_by_the_gate():
    readiness = Readiness()
    release = asyncio.Event()
    published = asyncio.Event()
    stopped = asyncio.Event()
    failures = []

    async def boot(publish):
        try:
            await release.wait()
            publish(Starlette())
            readiness.ready()
            published.set()
            await asyncio.Event().wait()
        finally:
            stopped.set()

    gate = ReadinessGate(readiness, boot, version="1+10.gabc", on_failure=failures.append)
    async with LocalService(gate, token="secret", readiness=readiness).serving() as url, httpx.AsyncClient(trust_env=False) as client:
        assert (await client.get(f"{url}/healthz")).status_code == 503
        assert (await client.get(url, headers={"X-Local-Token": "secret"})).status_code == 503
        release.set()
        await asyncio.wait_for(published.wait(), timeout=2)
        assert (await client.get(f"{url}/healthz")).status_code == 200
        assert (await client.get(url, headers={"X-Local-Token": "secret"})).status_code == 404
    assert stopped.is_set()
    assert failures == []


def test_boot_failure_is_retained_and_reported():
    readiness = Readiness()
    failures = []

    async def boot(publish):
        message = "store refused"
        raise ValueError(message)

    gate = ReadinessGate(readiness, boot, version="1", on_failure=failures.append, details=lambda: {"search": "warming"})
    with TestClient(gate) as client:
        response = client.get("/healthz")
        assert response.status_code == 503
        assert response.json()["stage"] == "refused"
        assert response.json()["search"] == "warming"
        assert str(gate.failure) == "store refused"
    assert failures == [gate.failure]
