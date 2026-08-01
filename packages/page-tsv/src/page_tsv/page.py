r"""Hybrid ``page-tsv`` encoder for ``Page[T]`` envelopes.

Output is JSON-shaped: envelope metadata stays structured, ``items`` is a single
TSV string, and ``_items_format = "tsv"`` discriminates from a plain JSON page
where ``items`` would be a list. Top-level wire format remains ``"json"``; agents
that don't know about ``_items_format`` still get a parseable JSON object with a
string ``items`` value (and can fall back to splitting on ``\n`` to inspect rows).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, get_args, get_origin

from lean_wire import encode_tsv

if TYPE_CHECKING:
    from page_tsv.response import Page


def _item_columns(page: Page) -> list[str]:
    """Pull the TSV header columns from the resolved item type's ``model_fields``.

    Falls back to the UNION of every item's dump keys when the type isn't
    statically resolvable (rare under the type-driven dispatch).
    """
    items_field = type(page).model_fields.get("items")
    if items_field is not None:
        ann = items_field.annotation
        if get_origin(ann) is list:
            args = get_args(ann)
            if len(args) == 1 and isinstance(args[0], type):
                item_cls = args[0]
                fields = getattr(item_cls, "model_fields", None)
                if fields is not None:
                    return list(fields.keys())

    # Fallback: the UNION of every item's keys, first-seen order. NOT the first
    # item's — a serializer that prunes empties emits heterogeneous rows, and
    # reading one of them as the schema silently deletes the keys it lacked.
    # See `render._derive_columns` for what that cost in production.
    columns: dict[str, None] = {}
    for item in page.items:
        if hasattr(item, "model_dump"):
            columns.update(dict.fromkeys(item.model_dump(mode="json")))
        elif isinstance(item, dict):
            columns.update(dict.fromkeys(str(k) for k in item))
    if columns:
        return list(columns)
    return []


def assemble_page_envelope(envelope_no_items: dict[str, Any], rows: list[Any], columns: list[str]) -> str:
    """Serialize a page-shaped dict into the wire JSON string.

    Take the envelope (with ``items`` already excluded), the row list, and the
    resolved TSV columns; return JSON with ``items`` replaced by a TSV blob and the
    ``_items_format`` discriminator set.
    """
    envelope: dict[str, Any] = dict(envelope_no_items)
    envelope["items"] = encode_tsv(rows, columns=columns)
    envelope["_items_format"] = "tsv"
    return json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)


def encode_page_tsv(page: Page) -> str:
    """Encode a ``Page[T]`` as a JSON envelope with an embedded TSV ``items`` string.

    The envelope also carries a ``_items_format = "tsv"`` discriminator.
    """
    return assemble_page_envelope(
        page.model_dump(mode="json", exclude={"items"}),
        list(page.items),
        _item_columns(page),
    )


__all__ = ["assemble_page_envelope", "encode_page_tsv"]
