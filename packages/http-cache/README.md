# http-cache

**Stop caring about the mechanics of an HTTP response cache.** Content-hash dedup, a
gzip-compressed body, TTL expiry, and conditional-GET (ETag / Last-Modified) — over one
sqlite file, keyed by `(url, variant)`. Composes
[`sqlite-resource`](../sqlite-resource) for the connection lifecycle.

```python
from pathlib import Path
from http_cache import HttpCache, conditional_headers

cache = HttpCache(Path("~/.app/http-cache.sqlite").expanduser())

row = await cache.get(url, variant=profile_hash)     # None if absent/expired
headers = conditional_headers(row)                   # If-None-Match / If-Modified-Since

# ... fetch with `headers`; on 200 store it, on 304 reuse row.body ...
await cache.put(
    url, variant=profile_hash,
    etag=resp.headers.get("etag"),
    last_modified=resp.headers.get("last-modified"),
    status_code=resp.status_code,
    content_type=resp.headers.get("content-type"),
    body=resp.content,
    ttl_s=900,
)
```

- **`variant`** — a caller-supplied cache-variant key (a hash of whatever the response
  varies by: proxy profile, auth, `Accept-Language`). Pass `""` when a URL caches
  uniformly. One URL, many variants.
- **Policy-free** — the store never decides *whether* to cache; the caller gates first
  (never cache an error page). It only reads and writes.
- **Composable** — `HttpCache` wraps a `SqliteResource`; or use the free functions
  `cache_get` / `cache_put` against any `aiosqlite.Connection`, with `apply_schema` as
  the `on_open` hook.

## Surface

- `HttpCache(db_path)` — `.get(url, variant="")`, `.put(url, variant="", *, etag, last_modified, status_code, content_type, body, ttl_s)`, `.close()`, async-CM
- `CacheRow` — the stored row (decompressed `body`)
- `conditional_headers(row) -> dict[str, str]`
- `cache_get(conn, url, variant="")`, `cache_put(conn, url, variant="", *, ...)`, `apply_schema(conn)`
