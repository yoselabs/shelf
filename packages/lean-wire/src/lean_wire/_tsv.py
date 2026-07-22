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


def encode_tsv(rows: list[Any], *, columns: list[str]) -> str:
    r"""Encode ``rows`` as line-oriented TSV with ``columns`` as the header.

    ``rows`` items may be pydantic ``BaseModel`` instances or plain dicts.
    ``columns`` SHOULD come from ``Model.model_fields.keys()`` (declared order)
    when the caller is type-driven; alphabetical sorting would defeat the point.
    Output is a header line followed by one line per row, each terminated by
    ``\\n`` — cells never contain a raw tab or newline (see module docstring).
    """
    lines = [_COL.join(_escape(c) for c in columns)]
    lines += [_COL.join(_row_cells(row, columns)) for row in rows]
    return _ROW.join(lines) + _ROW


__all__ = ["encode_tsv"]
