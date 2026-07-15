# page-tsv

Type-driven, consumer-aware rendering of tool results. The **whole wire format in
one owner**, so an LLM-facing renderer and a code/machine one can't drift.

## The seam

```python
from page_tsv import Page, render

class Task(BaseModel):
    id: int
    title: str

page = Page[Task](items=[Task(id=1, title="ship it")])

render(page, "llm")     # JSON envelope, items compressed to an embedded TSV string
render(page, "code")    # plain JSON — items stays a list of objects
```

`consumer` (`"llm"` / `"code"` / `"machine"`) is always a **caller-supplied
parameter**, never sniffed from ambient context. That is the whole trick: the
compression decision lives with the caller, and one implementation serves every
consumer.

## Type routing

`infer_format_hint` / `build_encoding_plan` map a return-type annotation to a
static plan, no runtime value needed:

| annotation | plan |
| --- | --- |
| `Page[ScalarRow]` | `page-tsv` (JSON envelope + embedded TSV `items`) |
| `list[ScalarRow]` | `tsv` |
| `Model` with a flat-array field | `envelope` (that field → TSV blob) |
| anything unproven-tabular | `json` |

"Scalar row" = a `BaseModel` whose fields are all scalar after
`model_dump(mode="json")`.

## After-the-fact encoders

A result middleware that only sees the already-plain payload (post-serialization)
uses `render_plain(payload, plan)`, `encode_page_tsv_dict(payload)`, and
`encode_envelope(value, tsv_fields)` to reproduce the same wire bytes.

## Composition

Built on [`lean-wire`](../lean-wire) for the line-oriented TSV codec and
empty-field pruning.
