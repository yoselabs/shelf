# html-fragment

**Turn a server-supplied HTML fragment into clean markdown or text.** Many sites hand
back their real content as a small HTML fragment rather than a full page — a Discourse
`cooked`, a Habr `textHtml`, a V2EX `content_rendered`, an HN Algolia comment `text`.
This primitive converts that fragment into link-preserving markdown or collapsed plain
text: lxml-backed, entity-decoded, and permissive (malformed HTML never raises).

```python
from html_fragment import to_markdown, to_text

to_markdown('<p>Hello <a href="https://example.com">there</a>.</p>')
# 'Hello [there](https://example.com).'

to_text("It&rsquo;s a test")          # "It’s a test"  — entities decoded
to_markdown('<a href="/rel">x</a>', base_url="https://e.com/foo/")
# '[x](https://e.com/rel)'             — relative hrefs absolutized
```

- **Link-preserving markdown** — paragraphs, `<br>`, `<li>`, `<em>`/`<i>`,
  `<strong>`/`<b>`, and `<a href>` survive; every other tag is stripped.
- **Entity-decoded** — `&rsquo;`, `&amp;`, numeric entities all resolve; `\xa0` and the
  narrow no-break space fold to a plain space.
- **Optional absolutization** — pass `base_url` and relative hrefs resolve absolute.
- **Never raises on malformed input** — lxml's permissive fragment parser tolerates
  unclosed tags and garbage; empty / whitespace-only input returns `""`.
- **Plain-text mode** — `to_text` strips all tags and collapses whitespace, for inline
  titles and bylines.

## Surface

- `to_markdown(html: str, *, base_url: str | None = None) -> str`
- `to_text(html: str) -> str`
