"""Boundary types for http-fetch — `FetchVerdict` + `FetchOutcome`."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class FetchVerdict(StrEnum):
    """Transport-layer outcome of a single HTTP fetch.

    Only the outcomes a pure HTTP primitive can determine. Policy verdicts
    (paywall, block-page, …) are the caller's concern, not the transport's.
    """

    ok = "ok"
    not_found = "not_found"
    rate_limited = "rate_limited"
    connection_error = "connection_error"
    dns_error = "dns_error"
    timeout = "timeout"
    proxy_unavailable = "proxy_unavailable"


@dataclass(slots=True, frozen=True)
class FetchOutcome:
    """One HTTP fetch's result — bytes + a closed verdict, never an exception.

    ``final_url`` is the URL after redirects. ``conditional_hit`` is ``True`` only
    for a ``304`` served against conditional headers; the body is then empty and the
    caller reuses its cached body.
    """

    body: bytes
    content_type: str
    status_code: int
    final_url: str
    headers: dict[str, str] = field(default_factory=dict)
    verdict: FetchVerdict = FetchVerdict.ok
    conditional_hit: bool = False
