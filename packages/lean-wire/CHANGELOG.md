# lean-wire CHANGELOG

Arrow-notation, AI-facing: `old shape ⇒ new shape`. One line per contract-shape change.

## lean-wire-v0.2.0

Additive. No existing call changes behaviour — every current caller passes
`columns=` explicitly and keeps exactly the bytes it had.

- `encode_tsv(rows, *, columns: list[str])` ⇒ `encode_tsv(rows, *, columns: list[str] | None = None)`. Omitting `columns` derives them via the new `derive_columns`. Migration: a caller that hand-rolls a column derivation should drop it and omit the argument; keep `columns=` only when you are type-driven and want a declared field order the rows may not fully populate.
- New export `derive_columns(rows) -> list[str]` — the UNION of every row's keys, first-seen order. Migration: replace any `rows[0]`-based derivation with this; reading one row as the schema deletes the keys that row happened to lack, silently.
