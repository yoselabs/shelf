# record-mine

**Recover the records an article extractor throws away.** A listing, an index, or a
threaded discussion page is not one article — it *is* N repeated records. Article
extractors (trafilatura and friends) locate one main-content node and discard the
repeated DOM structure as boilerplate, gutting exactly the content you wanted. This
package recovers it: a tree-aware detector locates the dominant repeated record region,
and a depth-aware renderer turns it into link-preserving markdown.

```python
from record_mine import extract_records

rs = extract_records(html, base_url="https://news.example.com")
if rs is not None:
    print(rs.to_markdown())        # "### Discussion (12 comments)" or "### Listing (30 records)"
    if rs.is_threaded:
        ...                        # nesting survived — depth per record
```

- **Tree-aware detection** — each `(tag, first-class-token)` signature is counted
  document-wide, so a recursively nested record region (a threaded comment tree) is
  located just as well as a flat sibling list.
- **Own-scope records** — a record's text and links exclude nested same-signature
  child-records, so an outer comment is never credited with its replies' content.
- **Depth-aware markdown** — a flat catalog row renders flush-left; a threaded reply is
  indented per nesting level so the conversation shape survives.
- **Self-gating** — three guards (non-empty class token, parent-signature consistency,
  heading presence) mean an article, a near-empty JS shell, or a reference doc yields
  `None`, and the caller falls through to another extraction source.
- **Pure** — HTML string in, records out; it never fetches, and the *policy* for what to
  do with the region lives above this primitive.

## Surface

- `extract_records(html: str, base_url: str = "") -> RecordSet | None`
- `Record` — `text, links, heading_text, heading_link, depth, markdown` (frozen, slotted)
- `RecordSet` — `records, container, child_signature, max_depth` (frozen, slotted); plus
  the `is_threaded` property and the `to_markdown()` method
