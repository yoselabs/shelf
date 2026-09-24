# convert-md changelog

Arrow-notation, AI-facing: one line per contract-shape change (old ⇒ new).

- 0.8.0 — `convert_html(html, *, url, source_kind)` ⇒ `convert_html(html, *, url, source_kind, include_links=False)` (additive; `include_links=True` keeps in-body anchors as `[label](url)` on the trafilatura path).
- 0.10.0 — new `missing_engines(suffixes) -> dict[str, list[str]]` (additive); each engine class gains `modules: tuple[str, ...]`.
