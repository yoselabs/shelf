"""Offline link liveness and public-network boundary scenarios."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar, Self

import pytest
from curl_cffi import CurlInfo, CurlOpt
from http_fetch import links
from http_fetch.links import LinkChecker, LinkReply, LinkState


async def public(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status,state", [(200, LinkState.alive), (404, LinkState.dead), (503, LinkState.dead)])
async def test_status_mapping(status: int, state: LinkState) -> None:
    async def open_link(url: str, method: str, ip: str, timeout_s: float) -> LinkReply:
        return LinkReply(status)

    result = await LinkChecker(resolver=public, opener=open_link).check("https://site.org")
    assert result.state is state
    assert result.reason == ("" if status == 200 else f"HTTP {status}")


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["http://127.0.0.1", "http://[::1]", "http://10.0.0.1", "http://169.254.169.254", "http://240.0.0.1"])
async def test_initial_private_host_refused(url: str) -> None:
    async def forbidden(url: str, method: str, ip: str, timeout_s: float) -> LinkReply:
        pytest.fail("private destination opened")

    assert (await LinkChecker(resolver=public, opener=forbidden).check(url)).state is LinkState.dead


@pytest.mark.asyncio
async def test_resolved_private_host_refused() -> None:
    async def private(host: str, port: int) -> list[str]:
        return ["93.184.216.34", "10.0.0.1"]

    assert (await LinkChecker(resolver=private).check("https://site.org")).state is LinkState.dead


@pytest.mark.asyncio
async def test_redirect_private_and_loop() -> None:
    calls = []

    async def redirect(url: str, method: str, ip: str, timeout_s: float) -> LinkReply:
        calls.append(url)
        return LinkReply(302, "http://127.0.0.1")

    checker = LinkChecker(resolver=public, opener=redirect, max_redirects=2)
    assert (await checker.check("https://site.org")).state is LinkState.dead
    assert len(calls) == 1

    async def loop(url: str, method: str, ip: str, timeout_s: float) -> LinkReply:
        calls.append(url)
        return LinkReply(302, "/again")

    calls.clear()
    result = await LinkChecker(resolver=public, opener=loop, max_redirects=2).check("https://site.org")
    assert result.reason == "redirect limit"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_head_fallback_and_timeout() -> None:
    methods = []

    async def fallback(url: str, method: str, ip: str, timeout_s: float) -> LinkReply:
        methods.append(method)
        return LinkReply(405 if method == "HEAD" else 200)

    assert (await LinkChecker(resolver=public, opener=fallback).check("https://site.org")).state is LinkState.alive
    assert methods == ["HEAD", "GET"]

    async def timeout(url: str, method: str, ip: str, timeout_s: float) -> LinkReply:
        raise TimeoutError

    assert (await LinkChecker(resolver=public, opener=timeout).check("https://site.org")).reason == "timeout"


@pytest.mark.asyncio
async def test_deadline_cancels_and_joins_workers() -> None:
    active = 0
    peak = 0

    async def blocked(url: str, method: str, ip: str, timeout_s: float) -> LinkReply:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.Event().wait()
        finally:
            active -= 1
        return LinkReply(200)

    checker = LinkChecker(resolver=public, opener=blocked)
    results = await checker.check_all([f"https://site.org/{i}" for i in range(5)], concurrency=2, deadline=0.01)
    assert all(r.state is LinkState.unknown for r in results.values())
    assert active == 0
    assert peak == 2


@pytest.mark.asyncio
async def test_rebinding_uses_validated_ip_and_refuses_private_peer() -> None:
    async def rebound(url: str, method: str, ip: str, timeout_s: float) -> LinkReply:
        assert ip == "93.184.216.34"
        return LinkReply(200, peer_ip="127.0.0.1")

    result = await LinkChecker(resolver=public, opener=rebound).check("https://site.org")
    assert result.state is LinkState.dead
    assert result.reason == "unsafe connected peer"


@pytest.mark.asyncio
async def test_transport_pins_ip_disables_proxy_and_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    # Any models curl_cffi's heterogeneous session keyword arguments at its boundary.
    class Session:
        def __init__(self, **options: Any) -> None:
            assert options["trust_env"] is False
            assert options["curl_options"][CurlOpt.RESOLVE] == [b"site.org:443:93.184.216.34"]
            assert options["curl_options"][CurlOpt.PROXY] == b""
            assert options["curl_options"][CurlOpt.NOBODY] == 1
            self.method = options["curl_options"][CurlOpt.CUSTOMREQUEST]

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def request(self, method: str, url: str, **options: Any) -> object:
            assert options["allow_redirects"] is False
            assert options["timeout"] == 15
            assert self.method == method.encode()

            class Response:
                status_code = 405 if method == "HEAD" else 200
                headers: ClassVar[dict[str, str]] = {}
                infos: ClassVar[dict[CurlInfo, bytes]] = {CurlInfo.PRIMARY_IP: b"93.184.216.34"}

            return Response()

    monkeypatch.setattr(links.requests, "AsyncSession", Session)
    result = await LinkChecker(resolver=public).check("https://site.org")
    assert result.state is LinkState.alive


@pytest.mark.asyncio
async def test_timeout_cancels_resolver_and_caller_cancellation_joins() -> None:
    active = 0
    entered = asyncio.Event()

    async def blocked(host: str, port: int) -> list[str]:
        nonlocal active
        active += 1
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            active -= 1
        return []

    checker = LinkChecker(resolver=blocked, timeout=0.01)
    assert (await checker.check("https://site.org")).reason == "timeout"
    assert active == 0
    entered.clear()
    batch = asyncio.create_task(checker.check_all(["https://site.org"]))
    await entered.wait()
    batch.cancel()
    with pytest.raises(asyncio.CancelledError):
        await batch
    assert active == 0


@pytest.mark.asyncio
async def test_production_dns_child_is_killed_and_reaped_on_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    entered = asyncio.Event()

    class Child:
        returncode: int | None = None
        reaped = False

        async def communicate(self) -> tuple[bytes, bytes]:
            entered.set()
            await asyncio.Event().wait()
            return b"[]", b""

        def kill(self) -> None:
            self.returncode = -9

        async def wait(self) -> int:
            self.reaped = True
            return self.returncode or 0

    child = Child()

    async def spawn(*args: object, **kwargs: object) -> Child:
        return child

    monkeypatch.setattr(links.asyncio, "create_subprocess_exec", spawn)
    checker = LinkChecker()
    task = asyncio.create_task(checker.check_all(["https://site.org"]))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert child.returncode == -9
    assert child.reaped
