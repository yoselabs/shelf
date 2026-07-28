# dom-schema

**Stop caring whether your site selectors still match** — declared CSS
extraction that reports *why* it yielded nothing, so a rotted scraper fails
loudly instead of answering "nothing here" forever.

## The problem

A site scraper returns `list[Row]`. The site changes its markup. The parse
returns `[]`. Every caller reads `[]` as *the page is empty* — because a list
cannot say anything else. Nothing raises, nothing warns, and the scraper goes
on producing that answer until somebody checks by hand.

This is not hypothetical. It was found in production twice on the same day, in
one codebase:

| parser | live page | returned |
|---|---|---|
| arXiv listing | 47 entries | `0` — regex wanted `href="`, arXiv serves `href ="` and single quotes |
| Wikipedia wikilinks | 1066 anchors | `0` — regex wanted `href="/wiki/X"`, Parsoid serves `href="./X"` |

Both had **green test suites**. Both fixtures were hand-written from the same
mental model as the parser, so they could only ever confirm that the parser
agreed with itself. And the live handler probe passed both — it checked that
content came back, which it did; the *index* was what had died.

## The fix

A `Schema` is **two-level**, and that is what makes the failure separable:

```python
from dom_schema import Schema, Field, Yield, extract

LISTING = Schema(
    container="dl#articles",          # where the region is
    row="dt", pair_with="dd",         # what one row is (here: a dt/dd pair)
    fields={
        "id":      Field(css="a[title='Abstract']", attr="href", required=True),
        "title":   Field(css="div.list-title", strip_prefix="Title:", required=True),
        "authors": Field(css="div.list-authors", strip_prefix="Authors:"),
    },
)

got = extract(html, LISTING)
```

| verdict | means | a fact about |
|---|---|---|
| `OK` | container matched, rows came out | — |
| `EMPTY` | container matched, held nothing | the **page** |
| `ROT` | container did not match | the **schema** |

A flat selector cannot supply that distinction, which is why `container` is
required rather than optional. `ROT` also covers the half-broken middle: rows
present structurally but every declared field selector missing — reporting
*that* as `EMPTY` would blame the page for the schema's failure.

`Extraction` is falsy on both `EMPTY` and `ROT`, so `if not got:` never
silently accepts an empty page as success; ask `got.verdict` to act on the
difference.

## Why not a regex

Because the failure mode is silence, and a *tolerant* regex only relocates it —
it survives the quote change that broke it this time and dies on the next
attribute reorder. A DOM parse is indifferent to quote style, attribute order,
and whitespace inside tags, none of which are part of a page's meaning.
`test_quote_style_and_whitespace_are_not_failure_modes` is the standing
evidence.

## Why not record-mine

[`record-mine`](../record-mine) *infers* the dominant repeated region on an
unknown page and returns generic records. `dom-schema` takes a *declared* shape
for a page you already know and returns named fields. Naming exposes more, but
requiring a selector removes working on unknown pages — so neither contains the
other, and they are two capabilities rather than one. Use `record-mine` when
you do not know the page; use `dom-schema` when you do and want to be told when
that stops being true.

## Fixtures are captured, never hand-written

`tests/fixtures/` holds real pages, fetched and committed. This is the one rule
the package cannot be honest without: a hand-written fixture encodes the same
assumption as the schema it tests, authored at the same moment by the same
person, so it cannot fail when that assumption is wrong about the site. It can
only confirm the schema agrees with itself — which is exactly how both parsers
above stayed green while dead.
