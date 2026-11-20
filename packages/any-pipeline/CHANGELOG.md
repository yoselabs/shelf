# Changelog

## 0.2.0

- New `FileStore(directory)`: a `Store[str]` (async `get(key) -> str | None`, `put(key, value)`), one file per key named `<readable prefix>-<sha256 of key>.txt`, written with `atomic_io.atomic_write_text`, directory created on first `put`. New dependency `atomic-io>=0.2,<1`.

## 0.1.0

- `Failed.cause` keeps the stage's own exception; `run_one` raises it; `Flow.otherwise(fallback)` turns a stage failure into a typed value (the record still shows it); two items with one key are refused; workers pull items instead of one task per item; `str(flow)` is its shape.
- Typed async stages, `>>`, `gather`, `Limit`, `run`, `Report`, `Persistent`, `blocking`.
