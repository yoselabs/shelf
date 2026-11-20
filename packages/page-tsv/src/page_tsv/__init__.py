"""page-tsv — type-driven, consumer-aware rendering of tool results.

The whole wire format in one owner, so it can't drift:

- ``Page[T]`` / ``Response`` — the paginated-result contract + encoded envelope.
- ``render_llm(value, *, plan)`` / ``render_json(value)`` — one rendering view per
  consumer, picked by the caller and never sniffed; ``render_llm`` compresses
  scalar tables to lean-wire TSV, ``render_json`` (code / machine) stays plain JSON.
- ``infer_format_hint`` / ``build_encoding_plan`` / ``EncodingPlan`` — the static
  type→format routing (``tsv`` / ``page-tsv`` / ``envelope`` / ``json``).
- ``encode_page_tsv`` + the ``render_plain`` / ``encode_*_dict`` family — the
  after-the-fact (already-plain-payload) encoders a result middleware uses.
- ``format_response`` — the legacy ``format_hint``-vocabulary adapter.

Composes ``lean-wire`` for the TSV codec + empty-field pruning.
"""

from __future__ import annotations

from page_tsv.formats import FormatHint, FormatName
from page_tsv.hint import format_response
from page_tsv.inference import (
    EncodingPlan,
    FormatHintInferred,
    build_encoding_plan,
    infer_format_hint,
    is_basemodel,
)
from page_tsv.page import assemble_page_envelope, encode_page_tsv
from page_tsv.render import (
    Rendered,
    encode_envelope,
    encode_page_tsv_dict,
    render_execute,
    render_json,
    render_llm,
    render_plain,
)
from page_tsv.response import Page, Response

__all__ = [
    "EncodingPlan",
    "FormatHint",
    "FormatHintInferred",
    "FormatName",
    "Page",
    "Rendered",
    "Response",
    "assemble_page_envelope",
    "build_encoding_plan",
    "encode_envelope",
    "encode_page_tsv",
    "encode_page_tsv_dict",
    "format_response",
    "infer_format_hint",
    "is_basemodel",
    "render_execute",
    "render_json",
    "render_llm",
    "render_plain",
]
