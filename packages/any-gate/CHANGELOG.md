# any-gate — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.1.0: `key(**parts) -> str` (32 hex, canonical JSON, order-free, refuses non-JSON); `Receipts(path, *, keep=50)` with `has(name, key) -> bool`, `record(name, key)`; file `{"version": 1, "receipts": {name: [keys, newest first]}}`.
