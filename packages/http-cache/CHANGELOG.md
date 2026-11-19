# Changelog

## 0.2.0

- Depends on content-digest: the stored `content_hash` is `digest_bytes(body, length=64)`, byte-identical to the former hashlib sha256 hex (golden test).

- The sqlite TTL table (expiry, lazy eviction, the SQL) moved to any-ttl-cache; http-cache keeps the `(url, variant)` keying, the gzip body, the content hash and the conditional-GET headers. `HttpCache(path, clock=)`, `cache_get(..., clock=)` and `cache_put(..., clock=)` take an injected clock (default `time.time`). The table schema and every stored byte are unchanged: a database written by 0.1.0 opens and reads as before (golden test over a fixture made with 0.1.0).
- Behaviour change on disk only: a read that finds an expired row now deletes it (and every other expired row), as llm-cache always did. A row that expired was never returned before and still is not.
- `test_property_positive_ttl_is_retrievable_immediately` runs on a fixed clock, so it no longer flakes under load (shelf-855).
