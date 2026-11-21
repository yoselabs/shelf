# jsonl-log — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.7.0: held-log key from `any_file.path_key` (same resolved text); requires `any-file>=0.3,<1`
- 0.6.0: breaking  ⇒  `read_only=` removed from `JsonlLog(...)` and `JsonlLog.open(...)`, `JsonlLog.read_only` removed; new `JsonlReader(path, *, keep=KEEP)` with `path`, `files()`, `records(decode)` (the old `open(path, read_only=True)`, no descriptor, no lock, no close); `JsonlLog.append -> None` (was `bool`, `False` only when read-only), `append_json -> None`, `append_at -> int` (was `int | None`); `rewrite` no longer has a read-only `0` return; requires `process-lock>=0.4,<1` and `atomic-io>=0.3,<1` (`rewrite` uses `atomic_replace_bytes`; same bytes and permissions)
- 0.4.0: `append`/`append_at` on a file replaced under all 4 attempts: silent success ⇒ raises new `LineLostError(JsonlLogError)`
- 0.4.0: `JsonlLog(path: str, rotate_lock=True)` AttributeError ⇒ accepted, `True` = `<path>.lock` for `Path` and `str`
- 0.4.0: evicted held log: reopened descriptor kept (leaked) ⇒ closed after each append
- 0.5.0: internal only, no contract change  ⇒  `HeldLogs._drop(key, evict=)` split into `_close(key)` and `_evict(key)` (no bool mode, Article III)
