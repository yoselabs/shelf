# Changelog

## 0.1.0

- `Failed.cause` keeps the stage's own exception; `run_one` raises it; `Flow.otherwise(fallback)` turns a stage failure into a typed value (the record still shows it); two items with one key are refused; workers pull items instead of one task per item; `str(flow)` is its shape.
- Typed async stages, `>>`, `gather`, `Limit`, `run`, `Report`, `Persistent`, `blocking`.
