"""Cancellable, public-network-only link liveness checks; no result cache."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import sys
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Literal
from urllib.parse import urljoin, urlsplit

from curl_cffi import CurlInfo, CurlOpt, requests
from curl_cffi.requests.exceptions import RequestException
from curl_cffi.requests.exceptions import Timeout as CurlTimeout


class LinkState(Enum):
    """Closed liveness verdict."""

    alive = "alive"
    dead = "dead"
    unknown = "unknown"


@dataclass(frozen=True)
class LinkResult:
    """A verdict and a diagnostic reason (empty for alive)."""

    state: LinkState
    reason: str = ""


@dataclass(frozen=True)
class LinkReply:
    """Opener response; redirects must not be followed by the opener."""

    status: int
    location: str = ""
    peer_ip: str = ""


Resolver = Callable[[str, int], Awaitable[list[str]]]
Opener = Callable[[str, Literal["HEAD", "GET"], str, float], Awaitable[LinkReply]]


def _public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast and not ip.is_reserved and not ip.is_unspecified


async def _resolve(host: str, port: int) -> list[str]:
    # getaddrinfo in an executor cannot be cancelled. A short-lived child can be
    # killed and reaped even when the system resolver hangs beyond our deadline.
    script = (
        "import json,socket,sys; "
        "print(json.dumps(list({r[4][0] for r in "
        "socket.getaddrinfo(sys.argv[1],int(sys.argv[2]),type=socket.SOCK_STREAM)})))"
    )
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-c",
        script,
        host,
        str(port),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        output, _ = await child.communicate()
        if child.returncode:
            msg = "DNS resolution failed"
            raise OSError(msg)
        values: object = json.loads(output)
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            msg = "invalid DNS response"
            raise OSError(msg)
        return [str(v) for v in values]
    finally:
        if child.returncode is None:
            child.kill()
        await child.wait()


async def _open(url: str, method: Literal["HEAD", "GET"], ip: str, timeout_s: float) -> LinkReply:
    parsed = urlsplit(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    address = f"[{ip}]" if ":" in ip else ip
    # Fresh handles prevent DNS/connection reuse. RESOLVE preserves Host and TLS
    # verification/SNI while pinning the actual connection; no ambient proxy.
    async with requests.AsyncSession(
        trust_env=False,
        curl_options={
            CurlOpt.RESOLVE: [f"{parsed.hostname}:{port}:{address}".encode()],
            CurlOpt.PROXY: b"",
            CurlOpt.NOBODY: 1,
            CurlOpt.CUSTOMREQUEST: method.encode(),
        },
        curl_infos=[CurlInfo.PRIMARY_IP],
    ) as session:
        response = await session.request(
            method,
            url,
            timeout=timeout_s,
            allow_redirects=False,
            headers={"User-Agent": "http-fetch link checker", "Accept": "*/*"},
        )
        peer = response.infos.get(CurlInfo.PRIMARY_IP, b"")
        return LinkReply(
            response.status_code, response.headers.get("Location", ""), peer.decode() if isinstance(peer, bytes) else str(peer)
        )


class LinkChecker:
    """HEAD then GET checks with injected cancellable resolver/opener/clock.

    Openers must connect to the supplied IP, preserve TLS hostname verification,
    disable proxies/redirects, close resources on cancellation, and return headers
    without consuming response bodies. Resolvers must also cooperate with cancellation.
    """

    def __init__(
        self,
        *,
        resolver: Resolver = _resolve,
        opener: Opener = _open,
        clock: Callable[[], float] = time.monotonic,
        timeout: float = 15,
        max_redirects: int = 5,
    ) -> None:
        if timeout <= 0 or max_redirects < 0:
            msg = "timeout must be positive and max_redirects nonnegative"
            raise ValueError(msg)
        self.resolver = resolver
        self.opener = opener
        self.clock = clock
        self.timeout = timeout
        self.max_redirects = max_redirects

    async def _address(self, url: str) -> str:
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            msg = "not an HTTP URL"
            raise ValueError(msg)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            ipaddress.ip_address(host)
        except ValueError:
            addresses = await self.resolver(host, port)
        else:
            addresses = [host]
        if not addresses or not all(_public(ip) for ip in addresses):
            msg = "unsafe host"
            raise ValueError(msg)
        return addresses[0]

    async def _request(self, url: str, method: Literal["HEAD", "GET"]) -> LinkReply:
        for hop in range(self.max_redirects + 1):
            async with asyncio.timeout(self.timeout):
                ip = await self._address(url)
                reply = await self.opener(url, method, ip, self.timeout)
            if reply.peer_ip and (not _public(reply.peer_ip) or ipaddress.ip_address(reply.peer_ip) != ipaddress.ip_address(ip)):
                msg = "unsafe connected peer"
                raise ValueError(msg)
            if reply.status not in (301, 302, 303, 307, 308):
                return reply
            if hop == self.max_redirects:
                msg = "redirect limit"
                raise ValueError(msg)
            if not reply.location:
                msg = "redirect without location"
                raise ValueError(msg)
            url = urljoin(url, reply.location)
        msg = "redirect limit"
        raise ValueError(msg)

    async def check(self, url: str) -> LinkResult:
        """Check an initial host and every redirect; failures are dead with reason."""
        try:
            reply = await self._request(url, "HEAD")
            if reply.status in (400, 403, 405, 406, 429, 501):
                reply = await self._request(url, "GET")
            if 200 <= reply.status < 400:
                return LinkResult(LinkState.alive)
            return LinkResult(LinkState.dead, f"HTTP {reply.status}")
        except (TimeoutError, CurlTimeout):
            return LinkResult(LinkState.dead, "timeout")
        except (OSError, ValueError, RequestException) as error:
            # Diagnostics omit URLs, which may contain consumer-owned credentials.
            reason = str(error) if isinstance(error, ValueError) else type(error).__name__
            return LinkResult(LinkState.dead, reason[:80])

    async def check_all(
        self,
        urls: Iterable[str],
        *,
        concurrency: int = 8,
        deadline: float = 120,
    ) -> dict[str, LinkResult]:
        """Distinct URLs; unfinished checks are unknown; all workers are joined."""
        if concurrency < 1 or deadline < 0:
            msg = "concurrency must be positive and deadline nonnegative"
            raise ValueError(msg)
        results = dict.fromkeys(urls, LinkResult(LinkState.unknown, "deadline"))
        pending = iter(results)
        end = self.clock() + deadline

        async def worker() -> None:
            for url in pending:
                if self.clock() >= end:
                    return
                results[url] = await self.check(url)

        tasks = [asyncio.create_task(worker()) for _ in range(min(concurrency, len(results)))]
        try:
            async with asyncio.timeout(max(0, end - self.clock())):
                await asyncio.gather(*tasks)
        except TimeoutError:
            pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        return results
