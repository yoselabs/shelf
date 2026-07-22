"""The consumer-aware rendering seam: ``render(value, consumer)`` for the llm / code / machine profiles.

``consumer`` is always a **caller-supplied parameter** — the renderer never sniffs
it from ambient call context. That is what keeps the whole wire format in one
owner: a caller that wants LLM-compressed output passes ``consumer="llm"``, a
code/machine caller passes its own value, and neither can drift from the other.
"""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Any, Literal

from lean_wire import dump_model_for_wire, encode_tsv
from pydantic import BaseModel

from page_tsv.inference import EncodingPlan, build_encoding_plan
from page_tsv.page import assemble_page_envelope, encode_page_tsv
from page_tsv.response import Page

if TYPE_CHECKING:
    from page_tsv.formats import FormatName

Consumer = Literal["llm", "code", "machine"]
"""A rendering consumer profile. Fixed by the caller (e.g. at server-build time
from a ``code_mode`` flag) — never sniffed from call context."""

_UNSET: Any = object()


def _json_default(obj: Any) -> Any:
    """Fall back for ``json.dumps`` — single-pass encoding straight from typed objects.

    A ``BaseModel`` is dumped via pydantic's own ``model_dump`` (one internal pass)
    plus the prune-empty marker if opted in; anything else degrades to ``str``.
    """
    if isinstance(obj, BaseModel):
        return dump_model_for_wire(obj)
    return str(obj)


def _encode_json(value: Any) -> str:
    """Compact JSON, single-pass — no normalize-then-encode double walk."""
    return json.dumps(value, separators=(",", ":"), default=_json_default, ensure_ascii=False)


def _to_plain(value: Any) -> Any:
    """Convert ``value`` to a JSON-able plain structure (the ``structured`` payload).

    ``BaseModel`` instances become ``model_dump(mode="json")`` dicts; dataclass
    instances become ``asdict`` dicts; ``list`` / ``tuple`` / ``dict`` containers
    recurse; scalars and arbitrary objects pass through.
    """
    if isinstance(value, BaseModel):
        return dump_model_for_wire(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    return value


def _derive_columns(rows: list[Any]) -> list[str]:
    """Derive TSV header columns from the first row.

    Declared model-field order for a ``BaseModel``, key order for a ``dict``.
    """
    if not rows:
        return []
    first = rows[0]
    if isinstance(first, BaseModel):
        return list(type(first).model_fields.keys())
    if isinstance(first, dict):
        return [str(k) for k in first]
    return []


def encode_envelope(value: Any, tsv_fields: tuple[str, ...]) -> str:
    """Encode a ``BaseModel`` envelope as JSON with embedded TSV strings.

    Every field stays JSON except those named in ``tsv_fields`` — each of those
    becomes a single TSV string with a ``_<field>_format = "tsv"`` discriminator
    alongside it, mirroring the page-tsv shape one level up.
    """
    if isinstance(value, BaseModel):
        envelope: dict[str, Any] = dump_model_for_wire(value)
    elif isinstance(value, dict):
        envelope = dict(value)
    else:
        # Plan said envelope but the value is not a model/dict — JSON it.
        return _encode_json(value)

    for name in tsv_fields:
        raw = envelope.get(name)
        rows = list(raw) if isinstance(raw, (list, tuple)) else []
        envelope[name] = encode_tsv(rows, columns=_derive_columns(rows))
        envelope[f"_{name}_format"] = "tsv"

    return _encode_json(envelope)


def encode_page_tsv_dict(payload: dict[str, Any]) -> str:
    """Page-tsv from an already-plain page dict (``{items, next_cursor, ...}``).

    The dict-input counterpart of :func:`page_tsv.page.encode_page_tsv` — used by a
    result middleware that sees the result only after it has been converted to
    plain JSON. Columns are row-derived (the generic-T model class is gone by this
    point).
    """
    items = payload.get("items")
    rows = list(items) if isinstance(items, (list, tuple)) else []
    envelope_no_items = {k: v for k, v in payload.items() if k != "items"}
    return assemble_page_envelope(envelope_no_items, rows, _derive_columns(rows))


def render_plain(payload: Any, plan: EncodingPlan) -> str:
    """Re-derive the compressed wire string from an already-plain payload.

    Follows a static :class:`EncodingPlan` — used by a result middleware that runs
    after the result is converted to plain dicts. Never called for ``kind="json"``.
    """
    if plan.kind == "tsv":
        rows = list(payload) if isinstance(payload, (list, tuple)) else []
        return encode_tsv(rows, columns=_derive_columns(rows))
    if plan.kind == "page-tsv":
        if isinstance(payload, dict):
            return encode_page_tsv_dict(payload)
        return _encode_json(payload)
    if plan.kind == "envelope":
        return encode_envelope(payload, plan.tsv_fields)
    return _encode_json(payload)


class Rendered:
    """A tool result encoded for one consumer.

    Carries ``text`` (the wire string), ``format`` (``"json"`` / ``"tsv"``), and the
    lazily-computed ``structured`` JSON-able payload (the structured-content channel).
    """

    __slots__ = ("_structured", "_value", "format", "text")

    def __init__(self, text: str, fmt: FormatName, value: Any, *, structured: Any = _UNSET) -> None:
        self.text = text
        self.format = fmt
        self._value = value
        self._structured: Any = structured

    @property
    def structured(self) -> Any:
        """The JSON-able plain payload (the structured-content channel), computed once."""
        if self._structured is _UNSET:
            self._structured = _to_plain(self._value)
        return self._structured

    def __repr__(self) -> str:
        return f"Rendered(format={self.format!r}, text=<{len(self.text)} chars>)"


def render(value: Any, consumer: Consumer, *, plan: EncodingPlan | None = None) -> Rendered:
    """Render ``value`` for ``consumer`` — the one rendering seam.

    The ``llm`` consumer compresses per ``plan`` (an :class:`EncodingPlan`); when
    no plan is supplied it is derived from the runtime type, which only detects a
    top-level tabular shape. The ``code`` and ``machine`` consumers never compress
    — they yield plain JSON and the structured payload.
    """
    if consumer != "llm":
        # code / machine — structured, never compressed.
        return Rendered(_encode_json(value), "json", value)

    if plan is None:
        plan = build_encoding_plan(type(value))

    if plan.kind == "tsv":
        rows = list(value) if isinstance(value, (list, tuple)) else []
        return Rendered(encode_tsv(rows, columns=_derive_columns(rows)), "tsv", value)

    if plan.kind == "page-tsv":
        if not isinstance(value, Page):
            # Plan said page-tsv but the value is not a Page — JSON fallback.
            return Rendered(_encode_json(value), "json", value)
        return Rendered(encode_page_tsv(value), "json", value)

    if plan.kind == "envelope":
        return Rendered(encode_envelope(value, plan.tsv_fields), "json", value)

    return Rendered(_encode_json(value), "json", value)


def _is_flat_record(item: Any) -> bool:
    """True when ``item`` is a dict whose values are all scalars (a TSV-able row).

    Only the dict's own values are inspected (head sample).
    """
    if not isinstance(item, dict):
        return False
    return all(not isinstance(v, (list, dict)) for v in item.values())


def render_execute(value: Any) -> Rendered:
    """Render a dynamically-typed output for the ``llm`` consumer by value inference.

    A head-uniform flat list encodes as TSV; anything else (or a TSV failure) falls
    back to JSON.
    """
    structured = _to_plain(value)

    if isinstance(structured, (list, tuple)) and structured and _is_flat_record(structured[0]):
        try:
            rows = list(structured)
            text = encode_tsv(rows, columns=_derive_columns(rows))
            return Rendered(text, "tsv", value, structured=structured)
        except Exception:  # noqa: BLE001, S110 -- non-uniform past the head → JSON fallback
            pass

    return Rendered(_encode_json(structured), "json", value, structured=structured)


__all__ = [
    "Consumer",
    "Rendered",
    "encode_envelope",
    "encode_page_tsv_dict",
    "render",
    "render_execute",
    "render_plain",
]
