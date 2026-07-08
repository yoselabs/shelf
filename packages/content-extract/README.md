# content-extract

**Turn a fetched web page into an article-shaped record.** Body Markdown, plus the
metadata an article extractor usually strips: title, byline, published date, a heading
outline, and role-classified links. The body Markdown is composed from
[`convert-md`](../convert-md)'s `convert_html` (trafilatura-first, url-aware,
never-raises); metadata comes from `trafilatura.extract_metadata`, and the outline +
links from `selectolax`.

```python
from content_extract import extract_markdown, parse_metadata

content = await extract_markdown(html, url="https://example.org/post/x")
print(content.title, content.published)     # "How adaptive web fetching…", date(2026, 4, 1)
for link in content.links:
    print(link.role, link.href)             # "nav" / "primary" / "footer" / "meta"

meta = parse_metadata(html)                 # {"og.title": …, "twitter.card": …, "jsonld[0].@type": …}
```

- **Composed body** — the Markdown comes straight from `convert_html(html, url=url).body_markdown`,
  so boilerplate removal and the never-raises contract are inherited, not re-implemented.
- **Role-classified links** — each anchor is tagged `primary` / `nav` / `meta` / `footer`
  by walking its DOM ancestors (closest semantic ancestor wins). Filtering is a caller concern.
- **Off-thread** — `extract_markdown` is async and punts the blocking parse to a worker
  thread; the sync internals never run on an async path directly.
- **Flat metadata** — `parse_metadata` returns dot-keyed OG / Twitter / first-JSON-LD
  fields; missing fields are omitted, not `None`.
- **Pure & reusable** — HTML string in, records out; it never fetches, and the presentation
  *policy* lives above this primitive. Zero consumer-domain imports.

## Surface

- `extract_markdown(html: str, url: str) -> ExtractedContent` (async)
- `parse_metadata(html: str) -> dict[str, str]`
- `ExtractedContent` — `content_md, title, byline, published, headings, links, score` (frozen, slotted)
- `ExtractedHeading` — `level, text` (frozen, slotted)
- `ExtractedLink` — `anchor, href, role` (frozen, slotted)
