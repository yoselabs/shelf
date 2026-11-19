# Changelog

## 0.2.0

- The sqlite TTL table (expiry, lazy eviction, the SQL) moved to any-ttl-cache; llm-cache keeps the `(key, model)` keying and the `anyllm.Completion` shape. `LlmCache(conn, ttl_s=, clock=)` takes an injected clock (default `time.time`). The table schema and every stored byte are unchanged: a database written by 0.1.2 opens and reads as before (golden test over a fixture made with 0.1.2).
