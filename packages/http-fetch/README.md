# http-fetch

**Stop caring about curl_cffi's session plumbing and exception zoo.** One async
callable that performs an HTTP GET with a browser TLS fingerprint and maps every
outcome — timeout, connection error, proxy failure, non-2xx, 304 — to a closed
verdict. It never raises on a routine failure.

```python
from http_fetch import fetch_bytes, FetchVerdict

out = await fetch_bytes(
    "https://example.com/",
    headers={"Accept": "text/html"},
    proxy_url=proxy,                 # optional; routing policy lives above this
    conditional_extras={"etag": row.etag, "last_modified": row.last_modified},
    breaker=host_breaker,            # optional duck-typed async-CM circuit breaker
)

if out.verdict is FetchVerdict.ok and not out.conditional_hit:
    save(out.body, out.content_type)
elif out.conditional_hit:
    reuse(cached_body)               # 304 — body is empty by design
```

- **Never raises on routine failure** — `FetchVerdict` is `ok / not_found /
  rate_limited / connection_error / timeout / proxy_unavailable`. Policy verdicts
  (paywall, block-page) are the caller's concern, not the transport's.
- **Policy injected, not owned** — proxy selection, retry, and stealth strategy sit
  *above* this primitive and pass in (`proxy_url`, `breaker`, `impersonate`). Nothing
  here reaches back into the app.
- **Conditional GET built in** — pass `conditional_extras`; a `304` returns
  `conditional_hit=True` with an empty body so the caller reuses its cache.
- **Secret-safe** — cookie and `Authorization` values never appear in this module's
  diagnostics.

## Surface

- `await fetch_bytes(url, *, headers=None, timeout_s=10.0, proxy_url=None, cookies=None, conditional_extras=None, impersonate="chrome120", breaker=None) -> FetchOutcome`
- `FetchOutcome` — `body, content_type, status_code, final_url, headers, verdict, conditional_hit`
- `FetchVerdict` — the closed transport verdict enum
- `conditional_headers(extras) -> dict[str, str]`

## Link liveness (0.4.0)

`LinkChecker` checks public HTTP(S) links, pins validated DNS addresses for TLS
connections, validates every redirect, and tries GET when HEAD is refused.
No result cache or consumer URL extraction, placeholder, or credential policy.

```python
from http_fetch import LinkChecker, LinkState

checker = LinkChecker(timeout=15, max_redirects=5)
result = await checker.check("https://example.com")
results = await checker.check_all(urls, concurrency=8, deadline=120)
if result.state is LinkState.dead:
    report(result.reason)
```

- `LinkChecker(*, resolver=..., opener=..., clock=..., timeout=15, max_redirects=5)`
- `await checker.check(url) -> LinkResult`: alive for 2xx or non-redirect 3xx;
  dead with reason for HTTP errors, unsafe hosts/peers, DNS/connection failures,
  timeout, malformed URLs, and exhausted redirects. HEAD 400/403/405/406/429/501
  retries with GET. Timeout covers DNS and opening each hop.
- `await checker.check_all(urls, *, concurrency=8, deadline=120) -> dict[str, LinkResult]`:
  distinct URLs; unfinished checks return unknown with reason `deadline`. Workers
  are cancelled and awaited on deadline or caller cancellation; no detached work.
- `LinkResult(state, reason="")` and `LinkState.alive / dead / unknown`.
- `LinkReply(status, location="", peer_ip="")`: response from an injected opener.
  Resolver signature: `async (host, port) -> list[str]`; all returned IPs must be
  public. Opener signature: `async (url, method, validated_ip, timeout_s) -> LinkReply`.
  It must connect only to that IP, preserve hostname TLS verification, disable
  proxies and redirects, return headers without consuming bodies, and clean up
  on cancellation. Resolver and opener must be cancellable. Clock is a monotonic
  seconds callable. Production DNS uses a cancellable, reaped subprocess rather
  than an executor thread; production requests use curl_cffi with proxies disabled.
