# json-in-html

**Stop caring about where a page hid its structured data.** Modern SPAs and most
product / article pages embed their real content as JSON — an LD-JSON schema, a
`<script type="application/json">` blob, HTML5 microdata, OpenGraph meta tags, or a
`window.<var> = {...}` assignment. Generic markdown extractors strip these. This
extractor scans an HTML string and hands back the parsed payloads, ranked by
downstream value. Malformed JSON is skipped, never raised.

```python
from json_in_html import extract_json_payloads, rank_payloads, is_answer_bearing

payloads = rank_payloads(extract_json_payloads(html))
if payloads and is_answer_bearing(payloads[0]):
    render(payloads[0].data)          # a Product / Article / LocalBusiness, ranked first
```

- **Six detectors, one call** — `__NEXT_DATA__`, `__NUXT_DATA__`, `application/ld+json`,
  generic `application/json`, HTML5 microdata, OpenGraph, and `window.<var>` state.
- **Ranked, not just found** — `rank_payloads` buckets strong schema (Product / Article
  / LocalBusiness with >=3 fields) ahead of framework app-state, ahead of metadata.
- **Answer vs. chrome** — `is_answer_bearing` tells a thin-but-complete Product page
  apart from navigation boilerplate.
- **Whole-body JSON too** — `parse_json_response` / `sniff_json_body` /
  `is_json_content_type` recover a JSON API response served under any content-type.
- **Never raises on routine failure** — a tag that fails to parse is dropped; the rest
  of the page still emits.

## Surface

- `extract_json_payloads(html) -> list[JsonPayload]`
- `rank_payloads(payloads) -> list[JsonPayload]`
- `is_answer_bearing(payload) -> bool`
- `parse_json_response(text) -> JsonPayload | None`
- `sniff_json_body(body: bytes) -> bool`
- `is_json_content_type(content_type: str | None) -> bool`
- `JsonPayload` — `source, data, script_id, byte_size` (frozen, slotted)
- `JsonSource` — the closed detector-identity literal
