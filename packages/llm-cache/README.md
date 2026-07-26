# llm-cache

A sqlite-backed TTL cache for LLM completions, keyed on `(key, model)`. Stop
caring about the sqlite plumbing of *"have I already asked this exact thing of
this exact model?"* — the cache stores and returns `anyllm.Completion`, the same
currency the provider returns, so a hit is a drop-in for a call.

```python
import aiosqlite
from anyllm import build_adapter
from llm_cache import LlmCache, make_key

conn = await aiosqlite.connect("app.db")
cache = LlmCache(conn, ttl_s=900)                      # 15-minute freshness window
provider = build_adapter("anthropic-api")

key = make_key(content, question, "my-template-v1")    # what determines answer identity
hit = await cache.get(key=key, model="claude-haiku-4-5")
if hit is None:
    hit = await provider.complete(user=question, model="claude-haiku-4-5")
    await cache.put(key=key, model="claude-haiku-4-5", completion=hit)
print(hit.text)
```

## Design

- **Policy-free key.** The cache does not know what a "prompt" is — only an opaque
  `key` string you compute (via `make_key`, or your own) from whatever determines
  answer identity: content, question, template, system prompt. `make_key(*parts)`
  hashes each part (sha256) and joins them; order matters.
- **Model is always a distinct slot.** A model swap never reads a stale answer.
- **Completion in, Completion out.** A hit carries the *original* cost, token
  counts, and latency of the cached call. The caller decides how to account for
  the (free) hit — e.g. zero `cost_usd`, stash the original.
- **Connection-agnostic.** You inject an open `aiosqlite.Connection` (e.g. from
  `sqlite-resource`); the cache owns its `llm_cache` table, never the connection
  lifecycle, so it shares one sqlite file with your other tables.
- **Self-expiring.** Entries expire after `ttl_s` and are evicted lazily on the
  read that surfaces them, plus a manual `evict_expired()`.
