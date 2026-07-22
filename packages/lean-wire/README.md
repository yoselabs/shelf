# lean-wire

Token-lean, agent-facing wire payloads. Two mechanisms, one job: stop a model
reading noise instead of data.

## `encode_tsv(rows, *, columns)` — line-oriented TSV

```python
from lean_wire import encode_tsv

encode_tsv([{"id": 1, "title": "alpha"}], columns=["id", "title"])
# 'id\ttitle\n1\talpha\n'
```

`rows` are pydantic `BaseModel` instances or plain dicts; `columns` set the
header and order (pass `Model.model_fields.keys()` for declared order). `list` /
`dict` cells are JSON-blobbed.

**Truly line-oriented** — the reason this isn't a stdlib `csv` writer: `csv` wraps
a cell containing a tab or newline in quotes but leaves the raw `\n` *inside* the
field, so an agent that splits the payload on `\n` tears one record into several.
`encode_tsv` instead escapes `\`, `\t`, `\n`, `\r` in every cell, so one record is
always exactly one physical line and one `\t` always separates two columns. The
escaping is reversible.

## `PruneEmpty` — drop empty fields on the wire

```python
from lean_wire import PruneEmpty

class AskExtraction(PruneEmpty):
    truncated: bool
    model: str | None = None
    tags: list[str] = []

AskExtraction(truncated=False).model_dump()
# {'truncated': False}   ← None / '' / [] / {} dropped; informative False kept
```

Empty means `None` / `""` / `[]` / `{}` only — falsy-but-informative values
(`0`, `False`, `Decimal(0)`) are kept. Cascades through nested models. The JSON
schema is unchanged; only the wire payload shrinks. Also exported: `prune_dict`
(free-function form) and `dump_model_for_wire` (the one wire-dump seam).

## Versioning

Semver is the **wire-format version**: any change to the bytes `encode_tsv`
emits is a breaking (major) change.
