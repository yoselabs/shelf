# http-fetch CHANGELOG

Arrow-notation, AI-facing: `old shape ⇒ new shape`. One line per contract-shape change.

## http-fetch-v0.2.0

- DNS-resolution failure verdict: `fetch_bytes(...) -> FetchOutcome(verdict=FetchVerdict.connection_error)` ⇒ `FetchVerdict.dns_error` (no proxy) / `FetchVerdict.proxy_unavailable` (proxy set). New member `FetchVerdict.dns_error`. Migration: consumers matching `connection_error` to catch DNS failures must also match `dns_error`; a genuine NXDOMAIN is now distinguishable from a network/connection drop.
