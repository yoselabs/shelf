# any-ttl-cache

**Stop re-writing "a row that stops being true after N seconds".** One owner of the sqlite TTL table: `put` stamps the expiry,
`get` returns a fresh row or `None` and deletes expired rows on the read that finds one, and time comes from an injected clock,
so a test steps time instead of sleeping. The caller keeps its keying, its value encoding and its schema.

```python
from any_ttl_cache import TtlTable

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    url TEXT NOT NULL, body BLOB NOT NULL, fetched_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
    PRIMARY KEY (url)
);
"""
pages = TtlTable(name="pages", keys=("url",), values=("body",), stamped="fetched_at", schema=SCHEMA, clock=clock)

await pages.ensure(conn)                                   # conn: an open aiosqlite.Connection you own
await pages.put(conn, ("https://x/",), (b"<html>",), ttl_s=900)
entry = await pages.get(conn, ("https://x/",))             # Entry(values=(b"<html>",), stamped=..., expires_at=...) or None
await pages.evict_expired(conn)                            # rows removed
```

| call | job |
|---|---|
| `TtlTable(name=, keys=, values=, stamped=, schema=, clock=time.time)` | describe one table; identifiers are validated because they are spliced into SQL |
| `ensure(conn)` | run the caller's schema, then check the declared columns and `expires_at` exist; idempotent |
| `get(conn, key)` | the fresh `Entry`, else `None`; an expired row found is deleted, with every other expired row |
| `put(conn, key, values, ttl_s=)` | insert or replace; `expires_at = int(clock()) + ttl_s`; a negative `ttl_s` is born expired |
| `evict_expired(conn)` / `count(conn)` | rows removed now / row count, expired included |

A row is fresh while `expires_at` is after now (`expires_at <= now` is expired), in whole seconds.

- **The schema stays yours.** The package never writes DDL, so an existing database's bytes do not depend on it.
  The table needs the key columns, the value columns, the stamp column and an integer `expires_at`.
- **Not here:** what a key means, how a value is encoded, validators like ETag, size caps. Those are policy;
  `llm-cache` and `http-cache` keep theirs. Row-count LRU caches (`anyembed`) have no expiry and are a different thing.
- **Connection:** you inject an open `aiosqlite.Connection` into every call; the table never opens or closes one.
  `sqlite-resource` is the usual owner of that lifecycle.

Executable acceptance: `tests/`. A test in `tests/test_arch_ttl_cache.py` keeps every SQL statement on an `expires_at` column inside this package.
