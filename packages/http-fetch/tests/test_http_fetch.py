"""http-fetch: pure helpers, then fetch_bytes across every verdict branch.

A fake AsyncSession is injected at the package's curl_cffi import path.
"""

from __future__ import annotations

from typing import Any, Self

from curl_cffi.requests import exceptions as ce
from http_fetch import FetchOutcome, FetchVerdict, conditional_headers, fetch_bytes
from http_fetch.fetch import _is_proxy_error, _status_to_verdict


class TestConditionalHeaders:
    def test_empty_extras(self) -> None:
        assert conditional_headers(None) == {}
        assert conditional_headers({}) == {}

    def test_etag_only(self) -> None:
        assert conditional_headers({"etag": '"abc"'}) == {"If-None-Match": '"abc"'}

    def test_last_modified_only(self) -> None:
        assert conditional_headers({"last_modified": "Wed, 21 Oct"}) == {"If-Modified-Since": "Wed, 21 Oct"}

    def test_both(self) -> None:
        out = conditional_headers({"etag": '"x"', "last_modified": "now"})
        assert out == {"If-None-Match": '"x"', "If-Modified-Since": "now"}

    def test_empty_string_etag_skipped(self) -> None:
        assert conditional_headers({"etag": ""}) == {}

    def test_non_string_value_skipped(self) -> None:
        bad: Any = {"etag": 12345}  # non-str value is the point: it must be skipped
        assert conditional_headers(bad) == {}


class TestIsProxyError:
    def test_proxy_keyword(self) -> None:
        assert _is_proxy_error(RuntimeError("proxy refused"))

    def test_socks_keyword(self) -> None:
        assert _is_proxy_error(RuntimeError("SOCKS5 handshake"))

    def test_tunnel_keyword(self) -> None:
        assert _is_proxy_error(RuntimeError("tunnel failed"))

    def test_non_proxy_error(self) -> None:
        assert not _is_proxy_error(RuntimeError("connection reset"))


class TestStatusToVerdict:
    def test_200_ok(self) -> None:
        assert _status_to_verdict(200) is FetchVerdict.ok

    def test_404_not_found(self) -> None:
        assert _status_to_verdict(404) is FetchVerdict.not_found

    def test_429_rate_limited(self) -> None:
        assert _status_to_verdict(429) is FetchVerdict.rate_limited

    def test_other_4xx_connection_error(self) -> None:
        assert _status_to_verdict(403) is FetchVerdict.connection_error

    def test_5xx_connection_error(self) -> None:
        assert _status_to_verdict(503) is FetchVerdict.connection_error


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        content: bytes = b"<html>ok</html>",
        content_type: str = "text/html",
        url: str = "https://example.com/",
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.url = url
        self.headers = {"content-type": content_type}


class _FakeSession:
    def __init__(self, payload: _FakeResponse | BaseException) -> None:
        self._payload = payload
        self.last_request: dict[str, Any] = {}
        self.session_kwargs: dict[str, Any] = {}

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.last_request = {"url": url, **kwargs}
        if isinstance(self._payload, BaseException):
            raise self._payload
        return self._payload


def _patch_session(monkeypatch: Any, payload: _FakeResponse | BaseException) -> _FakeSession:
    fake = _FakeSession(payload)

    def _factory(**kw: Any) -> _FakeSession:
        fake.session_kwargs = kw
        return fake

    monkeypatch.setattr("http_fetch.fetch.cr.AsyncSession", _factory)
    return fake


async def test_chrome_impersonation_is_default(monkeypatch: Any) -> None:
    fake = _patch_session(monkeypatch, _FakeResponse())
    await fetch_bytes("https://example.com/")
    assert fake.session_kwargs.get("impersonate", "").startswith("chrome")


async def test_impersonate_override(monkeypatch: Any) -> None:
    fake = _patch_session(monkeypatch, _FakeResponse())
    await fetch_bytes("https://example.com/", impersonate="safari17_0")
    assert fake.session_kwargs.get("impersonate") == "safari17_0"


async def test_200_returns_ok(monkeypatch: Any) -> None:
    _patch_session(monkeypatch, _FakeResponse(content=b"<html>hi</html>"))
    result = await fetch_bytes("https://example.com/")
    assert isinstance(result, FetchOutcome)
    assert result.verdict is FetchVerdict.ok
    assert result.status_code == 200
    assert result.body == b"<html>hi</html>"
    assert result.content_type == "text/html"
    assert result.conditional_hit is False


async def test_404_returns_not_found(monkeypatch: Any) -> None:
    _patch_session(monkeypatch, _FakeResponse(status_code=404))
    result = await fetch_bytes("https://example.com/missing")
    assert result.verdict is FetchVerdict.not_found


async def test_429_returns_rate_limited(monkeypatch: Any) -> None:
    _patch_session(monkeypatch, _FakeResponse(status_code=429))
    assert (await fetch_bytes("https://example.com/")).verdict is FetchVerdict.rate_limited


async def test_5xx_returns_connection_error(monkeypatch: Any) -> None:
    _patch_session(monkeypatch, _FakeResponse(status_code=503))
    assert (await fetch_bytes("https://example.com/")).verdict is FetchVerdict.connection_error


async def test_timeout_returns_timeout(monkeypatch: Any) -> None:
    _patch_session(monkeypatch, ce.Timeout("connect timeout"))
    result = await fetch_bytes("https://example.com/")
    assert result.verdict is FetchVerdict.timeout
    assert result.status_code == 0


async def test_generic_request_exception_returns_connection_error(monkeypatch: Any) -> None:
    _patch_session(monkeypatch, ce.RequestException("DNS failure"))
    assert (await fetch_bytes("https://example.com/")).verdict is FetchVerdict.connection_error


async def test_dns_error_without_proxy_returns_dns_error(monkeypatch: Any) -> None:
    # A genuine target NXDOMAIN — distinct from a generic connection_error so the
    # caller can treat it as terminal (a real browser cannot resolve it either).
    _patch_session(monkeypatch, ce.DNSError("Could not resolve host: nope.invalid"))
    result = await fetch_bytes("https://nope.invalid/")
    assert result.verdict is FetchVerdict.dns_error
    assert result.status_code == 0


async def test_dns_error_with_proxy_returns_proxy_unavailable(monkeypatch: Any) -> None:
    # With a proxy set the target host is resolved by the proxy; a local DNS
    # failure is the proxy host failing to resolve, not the target domain.
    _patch_session(monkeypatch, ce.DNSError("Could not resolve proxy: bad-proxy.invalid"))
    result = await fetch_bytes("https://example.com/", proxy_url="http://bad-proxy.invalid:8080")
    assert result.verdict is FetchVerdict.proxy_unavailable


async def test_proxy_error_with_proxy_url_returns_proxy_unavailable(monkeypatch: Any) -> None:
    _patch_session(monkeypatch, ce.RequestException("SOCKS5 proxy refused"))
    result = await fetch_bytes("https://example.com/", proxy_url="socks5://localhost:1080")
    assert result.verdict is FetchVerdict.proxy_unavailable


async def test_proxy_shaped_error_without_proxy_is_connection_error(monkeypatch: Any) -> None:
    _patch_session(monkeypatch, ce.RequestException("SOCKS5 refused"))
    assert (await fetch_bytes("https://example.com/")).verdict is FetchVerdict.connection_error


async def test_proxy_url_is_plumbed(monkeypatch: Any) -> None:
    fake = _patch_session(monkeypatch, _FakeResponse())
    await fetch_bytes("https://example.com/", proxy_url="http://proxy:8080")
    assert fake.last_request["proxies"] == {"http": "http://proxy:8080", "https": "http://proxy:8080"}


async def test_no_proxy_url_omits_proxies(monkeypatch: Any) -> None:
    fake = _patch_session(monkeypatch, _FakeResponse())
    await fetch_bytes("https://example.com/")
    assert "proxies" not in fake.last_request


async def test_cookies_forwarded(monkeypatch: Any) -> None:
    fake = _patch_session(monkeypatch, _FakeResponse())
    await fetch_bytes("https://example.com/", cookies={"sid": "x"})
    assert fake.last_request["cookies"] == {"sid": "x"}


async def test_empty_cookies_dict_not_forwarded(monkeypatch: Any) -> None:
    fake = _patch_session(monkeypatch, _FakeResponse())
    await fetch_bytes("https://example.com/", cookies={})
    assert "cookies" not in fake.last_request


async def test_304_returns_conditional_hit(monkeypatch: Any) -> None:
    _patch_session(monkeypatch, _FakeResponse(status_code=304, content=b""))
    result = await fetch_bytes("https://example.com/", conditional_extras={"etag": '"abc"'})
    assert result.verdict is FetchVerdict.ok
    assert result.status_code == 304
    assert result.conditional_hit is True
    assert result.body == b""


async def test_conditional_extras_become_request_headers(monkeypatch: Any) -> None:
    fake = _patch_session(monkeypatch, _FakeResponse())
    await fetch_bytes(
        "https://example.com/",
        headers={"User-Agent": "UA"},
        conditional_extras={"etag": '"abc"', "last_modified": "Wed, 21 Oct"},
    )
    sent = fake.last_request["headers"]
    assert sent["User-Agent"] == "UA"
    assert sent["If-None-Match"] == '"abc"'
    assert sent["If-Modified-Since"] == "Wed, 21 Oct"


async def test_custom_headers_forwarded(monkeypatch: Any) -> None:
    fake = _patch_session(monkeypatch, _FakeResponse())
    await fetch_bytes("https://example.com/", headers={"User-Agent": "MyAgent/1.0", "X-Custom": "v"})
    assert fake.last_request["headers"]["User-Agent"] == "MyAgent/1.0"
    assert fake.last_request["headers"]["X-Custom"] == "v"


class _FakeBreaker:
    def __init__(self, *, raise_on_enter: bool = False) -> None:
        self.entered = False
        self.raise_on_enter = raise_on_enter

    async def __aenter__(self) -> Self:
        if self.raise_on_enter:
            msg = "breaker open"
            raise RuntimeError(msg)
        self.entered = True
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


async def test_breaker_wraps_fetch(monkeypatch: Any) -> None:
    _patch_session(monkeypatch, _FakeResponse())
    breaker = _FakeBreaker()
    result = await fetch_bytes("https://example.com/", breaker=breaker)
    assert breaker.entered is True
    assert result.verdict is FetchVerdict.ok


async def test_breaker_open_returns_connection_error(monkeypatch: Any) -> None:
    _patch_session(monkeypatch, _FakeResponse())
    breaker = _FakeBreaker(raise_on_enter=True)
    result = await fetch_bytes("https://example.com/", breaker=breaker)
    assert result.verdict is FetchVerdict.connection_error


class _CountingBreaker:
    """A breaker that records what its context actually SAW.

    The pre-existing `_FakeBreaker` asserted only that `__aenter__` ran. That is
    the whole reason the defect survived: entering a breaker is not using one.
    What decides whether a real breaker ever opens is the exception type reaching
    `__aexit__`, and nothing looked at it.
    """

    def __init__(self) -> None:
        self.failures = 0
        self.calls = 0

    async def __aenter__(self) -> Self:
        self.calls += 1
        return self

    async def __aexit__(self, exc_type: object, *_: object) -> bool:
        if exc_type is not None:
            self.failures += 1
        return False


async def test_a_transport_failure_is_recorded_by_the_breaker(monkeypatch: Any) -> None:
    """The defect. `_do` maps every transport error to a verdict and returns
    normally, so the breaker context used to exit cleanly and could never open.
    """
    _patch_session(monkeypatch, ce.Timeout("slow"))
    breaker = _CountingBreaker()
    result = await fetch_bytes("https://example.com/", breaker=breaker)
    assert result.verdict is FetchVerdict.timeout  # the caller still sees a verdict, not a raise
    assert breaker.calls == 1
    assert breaker.failures == 1


async def test_a_served_response_is_not_recorded_by_the_breaker(monkeypatch: Any) -> None:
    """The anti-vacuity half, and a real policy statement.

    A `404` and a `429` are the SERVER ANSWERING — the host is up. Counting them
    would let one missing URL take a healthy host out of service for every other
    URL on it, so a breaker that trips on everything is a different bug from a
    breaker that trips on nothing. Without this test, "raise unconditionally"
    would pass the test above.
    """
    for status, verdict in ((200, FetchVerdict.ok), (404, FetchVerdict.not_found), (429, FetchVerdict.rate_limited)):
        _patch_session(monkeypatch, _FakeResponse(status_code=status))
        breaker = _CountingBreaker()
        result = await fetch_bytes("https://example.com/", breaker=breaker)
        assert result.verdict is verdict
        assert breaker.calls == 1
        assert breaker.failures == 0, f"a {status} must not count against the breaker"


async def test_the_sentinel_never_escapes(monkeypatch: Any) -> None:
    """`fetch_bytes` promises it never raises on a routine failure.

    The fix carries the failure into the breaker by raising, so the contract is
    only intact if that raise is caught on the way out — including when the
    breaker's own `__aexit__` re-raises rather than swallowing.
    """

    class _ReRaising(_CountingBreaker):
        async def __aexit__(self, exc_type: object, *_: object) -> bool:
            if exc_type is not None:
                self.failures += 1
            return False  # propagate

    _patch_session(monkeypatch, ce.ConnectionError("down"))
    breaker = _ReRaising()
    result = await fetch_bytes("https://example.com/", breaker=breaker)
    assert result.verdict is FetchVerdict.connection_error
    assert breaker.failures == 1


async def test_cookies_not_in_outcome_diagnostic_repr(monkeypatch: Any) -> None:
    _patch_session(monkeypatch, _FakeResponse())
    result = await fetch_bytes("https://example.com/", cookies={"sid": "supersecret"})
    assert "supersecret" not in repr(result)
