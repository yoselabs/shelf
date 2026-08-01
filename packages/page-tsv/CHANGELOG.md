# page-tsv CHANGELOG

Arrow-notation, AI-facing: `old shape ⇒ new shape`. One line per contract-shape change.

## page-tsv-v0.2.1

No contract-shape change and no byte change — recorded because the dependency
floor moved. The union-columns rule promoted one level down to its right owner:
`lean-wire` is the only party that knows what a TSV header has to promise, and
three callers here derived it by hand.

- internal — `render._derive_columns` and `page._item_columns`'s fallback ⇒ `lean_wire.derive_columns`. Dependency floor `lean-wire` ⇒ `lean-wire>=0.2`.

## page-tsv-v0.2.0

Four encoder corrections. Signatures are unchanged; **the emitted bytes change**, so
a consumer with golden wire fixtures must re-capture them. Every change removes
output that was wrong — nothing that was correct before is dropped.

- `encode_envelope(value, tsv_fields)` — a field ABSENT from the payload: `{"_x_format":"tsv","x":"\n"}` ⇒ omitted entirely. Migration: a consumer reading `x == "\n"` as "empty" must now read `"x" not in payload`; a field present as `[]` still encodes to `"\n"`, so "I looked and found nothing" stays distinguishable from "not applicable".
- `encode_envelope(value, tsv_fields)` — a field arriving as an already-encoded TSV `str`: `"\n"` (content discarded) ⇒ the string, unchanged, plus its `_x_format` discriminator.
- `encode_envelope(value, tsv_fields)` — a field whose rows are neither `BaseModel` nor `dict`: `raise TypeError` (aborting the WHOLE envelope's encode) ⇒ that field stays JSON with no `_x_format`, every other field encodes normally.
- `_derive_columns` / `page._item_columns` fallback — TSV header columns: `rows[0]`'s keys ⇒ the UNION of every row's keys, first-seen order. Migration: a table over heterogeneous rows gains the columns the first row lacked; sparse rows fill with an empty cell. No column is ever removed, so a reader keyed by column NAME is unaffected; a reader keyed by column INDEX must move to names.
