r"""Line-oriented TSV encoder.

Header is the caller-supplied ``columns`` list (declared field order, not
alphabetical). Each row is dumped via ``model_dump(mode="json")`` when the input
is a pydantic ``BaseModel`` so datetimes / UUIDs / enums become wire scalars;
plain dicts pass through. ``list`` / ``dict`` cell values are JSON-blobbed into a
single cell (compact separators, ``ensure_ascii=False``).

**Truly line-oriented (the invariant a stdlib ``csv`` writer does not give you).**
``csv`` with ``QUOTE_MINIMAL`` wraps a cell containing a tab or newline in quotes
but leaves the raw ``\\n`` *inside* the field — so a line-oriented reader that
splits the payload on ``\\n`` (exactly what a token-lean agent does) silently
tears one record into several. This codec instead **escapes** ``\\``, ``\t``,
``\n``, ``\r`` in every cell, so one record is always exactly one physical line
and one ``\t`` always separates two columns. The escaping is reversible
(``\\t`` / ``\\n`` / ``\\r`` / ``\\\\``); decode by unescaping if a consumer ever
needs the raw value back.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

_ROW = "\n"
_COL = "\t"


def _escape(text: str) -> str:
    """Make ``text`` safe for a one-line, tab-delimited cell (reversible)."""
    # Backslash first so we never double-escape an introduced escape.
    return text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        # JSON blob is single-line already (json.dumps escapes interior \n as \\n);
        # still run it through _escape so a stray literal control char cannot leak.
        return _escape(json.dumps(value, separators=(",", ":"), ensure_ascii=False))
    # Scalars stringify exactly as a stdlib csv writer would (bool -> "True"/"False",
    # int/float -> repr) — the ONLY behaviour change from the origin codec is the
    # per-cell escaping above/below; scalar rendering is preserved byte-for-byte.
    return _escape(value if isinstance(value, str) else str(value))


def _row_cells(row: Any, columns: list[str]) -> list[str]:
    if isinstance(row, BaseModel):
        dumped: dict[str, Any] = row.model_dump(mode="json")
    elif isinstance(row, dict):
        dumped = row
    else:
        msg = f"encode_tsv expected BaseModel or dict rows, got {type(row).__name__}"
        raise TypeError(msg)
    return [_cell(dumped.get(col)) for col in columns]


def derive_columns(rows: list[Any]) -> list[str]:
    """TSV header columns for ``rows``: the UNION of their keys, first-seen order.

    **Not ``rows[0]``'s keys.** Rows are heterogeneous by construction whenever a
    producer prunes empties (:class:`~lean_wire.PruneEmpty`) or elides a field at
    its default — which key sets a row carries is a property of its *data*, not
    of its type. Reading one row as the schema therefore silently DELETES every
    key that row happened to lack: no error, no short row, nothing about the
    output looks wrong.

    That is not hypothetical. Three separate callers derived columns by hand,
    all three read ``rows[0]``, and the live symptom was an operator hint eliding
    ``severity`` at ``info`` and carrying it at ``critical``: an info hint sorted
    first produced a table with NO severity column, so the loudest signal in the
    system reached the agent unmarked. The rule lives here now because deriving
    it is not the caller's job — :func:`encode_tsv` is the only party that knows
    what a header has to promise.

    A ``BaseModel`` row contributes its declared field order (its dump preserves
    it), so the all-models case is exactly the declared order it always was.
    Rows that are neither model nor dict contribute nothing here — they raise in
    :func:`encode_tsv`, which is where that belongs.
    """
    columns: dict[str, None] = {}  # dict, not set — insertion order is the contract
    for row in rows:
        if isinstance(row, BaseModel):
            columns.update(dict.fromkeys(type(row).model_fields))
        elif isinstance(row, dict):
            columns.update(dict.fromkeys(str(k) for k in row))
    return list(columns)


def encode_tsv(rows: list[Any], *, columns: list[str] | None = None) -> str:
    r"""Encode ``rows`` as line-oriented TSV with ``columns`` as the header.

    ``rows`` items may be pydantic ``BaseModel`` instances or plain dicts.

    Omit ``columns`` to take :func:`derive_columns` — the union of every row's
    keys, which is what a header has to promise and what a hand-rolled
    derivation reliably gets wrong. Pass it explicitly when you are type-driven
    and want the declared field order of a type the rows may not fully populate
    (``Model.model_fields.keys()``); alphabetical sorting would defeat the point
    either way.

    A column no row carries renders as an empty cell, so a wider header never
    shifts a sparse row's values. Output is a header line followed by one line
    per row, each terminated by ``\\n`` — cells never contain a raw tab or
    newline (see module docstring).
    """
    header = derive_columns(rows) if columns is None else columns
    lines = [_COL.join(_escape(c) for c in header)]
    lines += [_COL.join(_row_cells(row, header)) for row in rows]
    return _ROW.join(lines) + _ROW


__all__ = ["derive_columns", "encode_tsv"]
