# Promote content-digest from ogy

ogy (the requirements knowledge base) hashes snapshots and evidence text with a hand-written convention:
`json.dumps(sort_keys, default=str)`, sha256, first 12 hex. `default=str` makes a datetime and its string hash
alike. any-frontmatter (`version.py`) and blueprint (`runner.py`) hash by hand the same way.

Add `content-digest` 0.1.0, stdlib only: `digest(value, *, length=12)` and `digest_text(text, *, length=12)`.
`digest` refuses non-JSON types, NaN/infinity and non-string keys. Additive; no existing package changes.
