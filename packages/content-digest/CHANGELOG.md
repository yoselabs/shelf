# content-digest — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.1.0: `digest(value, *, length=12) -> str` (sha256 of canonical JSON, sorted keys, compact, UTF-8; non-JSON types, NaN/inf and non-str keys refused); `digest_text(text, *, length=12) -> str`; `length` 1..64 else `ValueError`.
