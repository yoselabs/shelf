# any-markdown

**Stop caring where markdown hides its code.** Read the `[[wikilinks]]` a document actually
makes — never the ones inside a code block or a code span — and rewrite them in place under the
same rule.

```python
from any_markdown import Markdown

doc = Markdown.from_path(note)          # body read on first use, then kept
for link in doc.wikilinks:              # code-span examples are not here
    resolve(link.anchor, link.name, link.span)

doc.replace_wikilinks(retitle).text     # same exclusion on the way out

doc.sections                            # every heading's subtree, GitHub-slug ids
s = doc.section("scope--goals")         # or "lines:40-80", "lines:3:0-9000"
doc.text[s.start:s.end]
line_parts(transcript, 11_000, measure=wire_bytes)  # no headings: cut at blank lines
doc.chunks(size=1100, overlap=150)      # search windows: line, headings, section id
```

## What this package knows

**1. The links are one regex; knowing which ones are real is the whole CommonMark block
grammar.** `[[anchor|name]]` is MediaWiki's spelling, popularized by Obsidian, and it is not
CommonMark — so no markdown library extracts it. That makes hand-rolling look cheap, and it is,
right up to deciding whether a given `[[x]]` is a link or someone writing *about* the syntax. A
knowledge base that holds notes on its own conventions has both, often in the same file.

**2. A regex approximation of "where is the code" fails in ways you will not notice.** Measured
against the spec, the obvious hand-rolled scanner (fenced blocks by marker line, inline spans by
backtick pairs) misses an indented four-space code block entirely, and lets a short closing fence
(` ``` `) close a longer opening one (` ```` `). Both are silent: the extra links look real.

**3. And the naive repair is worse than the bug.** "A four-space indent means code" breaks
indented continuation lines inside a list, which are prose and commonly carry real links. The
only way to get this right is the block grammar, so the block scan here is `markdown-it-py`'s,
not ours. Inline spans are then found only in what the parser left as prose — so a fence's
contents are never re-scanned for backticks.

**4. The rewrite path is where the mistake costs a file.** Reading a phantom link produces a
spurious warning; *rewriting* one edits the user's document — a note demonstrating
`[[136|Old Title]]` silently rewritten when node 136 is retitled. `replace_wikilinks` shares
`wikilinks`' exclusion for exactly this reason: one scan, one answer, reader and writer alike.

**5. A section id is a promise to a client, so the heading scan is a line rule, not the
grammar.** A section is an ATX heading plus its subtree, id'd by GitHub's slug, deduped
`-2`, `-3` in document order. Ids are handed out and come back later, so they must not move
when a parser's reading of an edge case does; the scan is `ATX_HEADING_RE` outside a
` ``` ` / `~~~` fence. Text with no heading to cut at (a transcript, a dump, one table) is
addressed by `lines:A-B`, and a line too long for one part by `lines:N:A-B` (characters of
line N), cut at word breaks. How big a part may be is the caller's `measure` — characters
by default, wire bytes when that is what it pays for.

**6. A search hit is only useful if it opens where it was found.** `.chunks()` packs each
heading span into overlapping windows and tags every window with its start line, the
headings above it and the section id that `.section()` takes back — inside a line longer
than `part`, the characters it holds, so a hit deep in a one-line transcript opens there.

## The surface

| | |
|---|---|
| `Markdown(text)` / `Markdown.from_path(p)` | the document; `from_path` defers the read |
| `.text` · `.path` | source, and where it came from |
| `.wikilinks` | `Sequence[WikiLink]` in document order |
| `.replace_wikilinks(fn)` | a new `Markdown`; returning `link.text` is the no-op |
| `.code_spans` · `.is_code(pos)` | the code regions themselves |
| `.tokens` | the markdown-it token stream — the escape hatch |
| `.sections` · `.section(id)` | heading subtrees in order; one by slug or `lines:` id, else `None` |
| `Section` | `.id` `.heading` `.level` (0 = line part) `.chars` `.start` `.end` |
| `.chunks(size, overlap, part=None, measure=len)` | `Chunk` `.line` `.text` `.section` `.headings` |
| `line_parts(text, budget, measure=len, base_line=1)` | `text` cut into `lines:` parts that cover it |
| `slug(heading)` · `clip(text, budget, measure=len)` · `ATX_HEADING_RE` | the pieces, for a caller with its own policy |
| `WikiLink` | `.anchor` `.name` `.span` `.text` `.display` |
| `parse_one(v)` · `anchor_of(v)` | for one authored value, not a document |

`name` is `None` when the link was written without a display half, and `""` when written as
`[[a|]]` — absent and empty are different things.

## What stays with the caller

Resolution — turning an anchor into whatever the app calls a target — is the app's business, and
so is any identity rule underneath it (id padding, slug rules, ambiguity policy). This package
tells you what was written and where; it has never heard of your URI scheme. Likewise for
sections: how much of a document one response may carry, what a cut view shows first, and
which ids a client is offered are the app's read policy — this package cuts and finds.
