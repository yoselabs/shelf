# json-in-html CHANGELOG

Arrow-notation, AI-facing: `old shape ⇒ new shape`. One line per contract-shape change.

## json-in-html-v0.2.0

- New: `microdata_to_ld(data) -> list[dict]` — flatten a `source="microdata"` payload's `{"type": [...], "properties": {...}}` shape into LD-JSON shape, so one walker consumes `ld_json` and `microdata` alike. The package already decoded this shape internally (`rank_payloads` scores microdata by reaching into it), so emitting it raw meant every consumer wrote a private adapter before the source was usable. `@type` preserves list-ness: list in, list out — collapsing a one-element list would invent a distinction the source does not make.
- New: `ld_entries(data) -> list[dict]` — the entity entries of an LD-JSON payload whatever container it arrived in (bare object / list / `@graph`). `@graph` is the one that bites: the outer object looks like a valid entity, so a consumer that does not descend finds ONE contentless entry rather than none, which reads as "this page has little structured data" rather than as a bug.
- Both additive; no existing behaviour changes.

## json-in-html-v0.1.0

- Initial promotion from a2web (`packages/json_in_script`).
