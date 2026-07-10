# content-extract changelog

Arrow-notation, AI-facing: one line per contract-shape change (old ⇒ new).

- 0.2.0 — `extract_markdown(html, url)` ⇒ `extract_markdown(html, url, *, include_links=False)` (additive; threads through to `convert_html`). Label-less `mailto:`/`tel:` anchors are now retained with an href-derived label (were dropped).
