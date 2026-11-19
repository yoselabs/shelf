# fts-query — changelog

AI-facing only: one line per contract-shape change, arrow notation.

## 0.2.0

- `Tokens` opened a raw `sqlite3.connect(":memory:")`  ⇒  `sqlite_sidecar.connect(":memory:")`; same behaviour, no stored bytes involved
- new dep: `sqlite-sidecar>=0.3`
