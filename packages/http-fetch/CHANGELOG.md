# http-fetch CHANGELOG

Arrow-notation, AI-facing: `old shape ⇒ new shape`. One line per contract-shape change.

## http-fetch-v0.3.0

- Injected circuit breaker, behaviour: `fetch_bytes(url, breaker=b)` on a transport failure ⇒ the failure is now RECORDED by `b` (it was not). `_do` maps every transport error to a `FetchVerdict` and returns normally, so the breaker context always exited cleanly and could never open — verified against a real `purgatory` breaker: five consecutive connection failures at `default_threshold=2` left it `closed` with `failure_count=0`. Migration: consumers passing `breaker=` get a breaker that opens for the first time; a host that is genuinely down will now short-circuit to `connection_error` instead of re-dialling every call. Nothing changes for callers that pass no breaker.
- Breaker failure policy (new, explicit): `timeout` / `connection_error` / `dns_error` / `proxy_unavailable` count against the breaker; `ok` / `not_found` (404) / `rate_limited` (429) do NOT — those are the server answering, and counting them would take a healthy host out of service over one missing URL.
- `fetch_bytes` still never raises on a routine failure; the fix carries the failure into the breaker via a private sentinel that is caught before returning.

## http-fetch-v0.2.0

- DNS-resolution failure verdict: `fetch_bytes(...) -> FetchOutcome(verdict=FetchVerdict.connection_error)` ⇒ `FetchVerdict.dns_error` (no proxy) / `FetchVerdict.proxy_unavailable` (proxy set). New member `FetchVerdict.dns_error`. Migration: consumers matching `connection_error` to catch DNS failures must also match `dns_error`; a genuine NXDOMAIN is now distinguishable from a network/connection drop.
