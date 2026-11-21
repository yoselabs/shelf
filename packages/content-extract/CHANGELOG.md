# content-extract changelog

Arrow-notation, AI-facing: one line per contract-shape change (old ⇒ new).

- 0.2.0 — `extract_markdown(html, url)` ⇒ `extract_markdown(html, url, *, include_links=False)` (additive; threads through to `convert_html`). Label-less `mailto:`/`tel:` anchors are now retained with an href-derived label (were dropped).

- 0.4.0: `extract` no longer swallows selectolax/link-extraction errors (they propagate)  ⇐  v0.3.0 returned empty headings and links on any `Exception`
