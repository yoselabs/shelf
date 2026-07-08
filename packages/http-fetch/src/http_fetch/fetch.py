"""The single HTTP-GET primitive — curl_cffi with browser TLS impersonation.

`fetch_bytes` performs one GET via :class:`curl_cffi.requests.AsyncSession` with a
browser JA3/JA4 TLS fingerprint, optional proxy, optional cookies, conditional-GET
headers, and an optional injected circuit breaker. It never raises on a routine
failure (timeout, connection error, proxy error, non-2xx) — every outcome maps to a
:class:`FetchVerdict` on the returned :class:`FetchOutcome`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from curl_cffi import requests as cr
from curl_cffi.requests import exceptions as ce

from .models import FetchOutcome, FetchVerdict

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

_DEFAULT_IMPERSONATE = "chrome120"
_DEFAULT_TIMEOUT_S = 10.0


def conditional_headers(extras: dict[str, str] | None) -> dict[str, str]:
    """Translate cached ``etag`` / ``last_modified`` values into conditional-GET headers.

    Robust to missing, blank, or non-string values.
    """
    if not extras:
        return {}
    out: dict[str, str] = {}
    etag = extras.get("etag")
    if isinstance(etag, str) and etag:
        out["If-None-Match"] = etag
    last_modified = extras.get("last_modified")
    if isinstance(last_modified, str) and last_modified:
        out["If-Modified-Since"] = last_modified
    return out


def _is_proxy_error(exc: BaseException) -> bool:
    # curl_cffi surfaces proxy failures via a generic RequestException; the message
    # names the transport ("proxy" / "socks" / "tunnel").
    msg = str(exc).lower()
    return "proxy" in msg or "socks" in msg or "tunnel" in msg


def _status_to_verdict(status: int) -> FetchVerdict:
    if status == 404:
        return FetchVerdict.not_found
    if status == 429:
        return FetchVerdict.rate_limited
    if status >= 400:
        return FetchVerdict.connection_error
    return FetchVerdict.ok


def _failure(url: str, verdict: FetchVerdict) -> FetchOutcome:
    return FetchOutcome(body=b"", content_type="", status_code=0, final_url=url, headers={}, verdict=verdict)


async def fetch_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    proxy_url: str | None = None,
    cookies: dict[str, str] | None = None,
    conditional_extras: dict[str, str] | None = None,
    impersonate: str = _DEFAULT_IMPERSONATE,
    breaker: AbstractAsyncContextManager[object] | None = None,
) -> FetchOutcome:
    """Issue one HTTP GET via curl_cffi with browser TLS impersonation.

    Returns a :class:`FetchOutcome` with a closed :class:`FetchVerdict`; never raises
    on routine failures. On a ``304`` paired with ``conditional_extras`` the result has
    ``conditional_hit=True`` and an empty body — the caller reuses its cached body.

    Cookie values and ``Authorization`` header values must never appear in diagnostic
    output produced by this module.

    Args:
        url: The absolute URL to GET.
        headers: Extra request headers (merged with conditional-GET headers).
        timeout_s: Per-request timeout in seconds.
        proxy_url: Optional proxy applied to both http and https.
        cookies: Optional cookie jar for the request.
        conditional_extras: Cached ``etag`` / ``last_modified`` for conditional GET.
        impersonate: curl_cffi impersonation profile (browser TLS fingerprint).
        breaker: Optional async context manager (a circuit breaker); a raise on entry
            maps to ``connection_error``.
    """
    request_headers: dict[str, str] = dict(headers or {})
    request_headers.update(conditional_headers(conditional_extras))

    async def _do() -> FetchOutcome:
        request_kwargs: dict[str, object] = {
            "headers": request_headers,
            "timeout": timeout_s,
            "allow_redirects": True,
        }
        if proxy_url:
            request_kwargs["proxies"] = {"http": proxy_url, "https": proxy_url}
        if cookies:
            request_kwargs["cookies"] = dict(cookies)
        # `impersonate` is a wide curl_cffi Literal; keep the public API a plain str and
        # unpack through an Any-typed mapping so the transport stays backend-agnostic.
        session_kwargs: dict[str, Any] = {"impersonate": impersonate}
        async with cr.AsyncSession(**session_kwargs) as session:
            try:
                response = await session.get(url, **request_kwargs)
            except ce.Timeout:
                return _failure(url, FetchVerdict.timeout)
            except ce.RequestException as exc:
                if proxy_url and _is_proxy_error(exc):
                    return _failure(url, FetchVerdict.proxy_unavailable)
                return _failure(url, FetchVerdict.connection_error)

        content_type = response.headers.get("content-type", "")
        response_headers = dict(response.headers)
        if response.status_code == 304:
            return FetchOutcome(
                body=b"",
                content_type=content_type,
                status_code=304,
                final_url=str(response.url),
                headers=response_headers,
                verdict=FetchVerdict.ok,
                conditional_hit=True,
            )
        return FetchOutcome(
            body=response.content,
            content_type=content_type,
            status_code=response.status_code,
            final_url=str(response.url),
            headers=response_headers,
            verdict=_status_to_verdict(response.status_code),
        )

    if breaker is None:
        return await _do()

    try:
        async with breaker:
            return await _do()
    except Exception:  # noqa: BLE001 — the breaker is duck-typed; any open/entry error is a connection failure
        return _failure(url, FetchVerdict.connection_error)
