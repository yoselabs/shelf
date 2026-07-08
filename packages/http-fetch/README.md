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
