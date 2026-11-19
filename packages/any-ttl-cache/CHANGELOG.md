# Changelog

## 0.2.0

- `# Any: <reason>` on the public signature that names `Any`; no behaviour or stored byte changes (shelf public-any rule, tests/test_arch_public_any.py)

## 0.1.0

- `TtlTable`, `Entry`: the sqlite TTL table with expiry, lazy eviction on read and an injected clock, extracted from llm-cache 0.1.2 and http-cache 0.1.0 (the same store written twice). The caller owns the schema text, so existing databases keep their bytes.
