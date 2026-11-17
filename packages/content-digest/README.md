# content-digest

**Stop caring how to hash a value so the same data always gets the same id.** Standard library only.

```python
from content_digest import digest, digest_text

digest({"b": 1, "a": [1, 2]})   # same as the keys the other way round; 12 hex characters
digest(value, length=64)        # the full sha256
digest_text("any text")         # sha256 of the UTF-8 bytes, 12 hex characters
```

## Rules

- `digest` hashes canonical JSON: sorted keys, compact separators (`,` `:`), UTF-8, non-ASCII kept.
- It refuses what JSON cannot say: a datetime, set, bytes or any other object raises `TypeError`; NaN and infinity
  raise `ValueError`; a non-string key raises `TypeError` (JSON would turn `1` into `"1"` and collide with it).
  There is no `default=str`, so a datetime and its string never hash alike. Convert first, on purpose.
- Tuples hash as lists. List order matters; key order does not.
- `digest_text` is the plain text form, not the JSON of a string: `digest("x") != digest_text("x")`.
- `length` is 1..64 (default 12); a longer digest starts with the shorter one. Outside the range raises `ValueError`.
- The digest is a short identity for display and change detection, not a security boundary.
