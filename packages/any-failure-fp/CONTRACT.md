# Failure fingerprints, storms, streaks, backoff

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

- `fingerprint(text, *, ids=None, tail=120) -> str`: pure and deterministic; `""` for empty or all-punctuation text.
  Same cause with different ids, paths, urls, shas, uuids, sessions, quoted payloads or numbers gives the same
  string; `ids` adds host patterns as `<label>`. Over `tail` characters the slug is cut to `tail - 8`, then `#` and 8 hex
  digits of the sha1 of the full slug. `head` strips that suffix.
- `trip(...) -> Trip | None`: distinct keys sharing `fp` inside the window, the recorded failure included, at least `min_keys`.
- `streak(...) -> int`: 1 plus earlier events of `key` with `fp`, newest first, ending at the first `stop` event.
- `seen_within(...) -> bool`: an event with the same key, kind and fp at or after `now - window_s`.
- `backoff(...) -> float`: `min(base * 2**clamp(attempt, 0, 63), cap) * (1 - jitter + 2 * jitter * rand())`.

No consumer app is imported. Executable acceptance: `tests/`.
