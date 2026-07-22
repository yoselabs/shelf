"""mcp-result-wire — FastMCP result middleware for token-lean, projected tool output.

Two ``fastmcp`` middlewares, driven by explicit per-tool registries (never sniffed
from framework metadata), composing ``page-tsv`` for the encoding:

- ``FormatRoutingMiddleware(plans, consumer, ...)`` — re-derive a tool's ``content``
  channel from its :class:`~page_tsv.EncodingPlan` (TSV / page-tsv / envelope) for the
  ``llm`` consumer, leaving ``structured_content`` canonical. ``code`` / ``machine``
  consumers pass through.
- ``ListViewMiddleware(settings)`` — project list rows to ``default_fields`` and
  paginate to ``page_size`` per :class:`ListViewSettings`.

Register format-routing *outermost* (before list-view) so ``content`` is derived from
the already-projected ``structured_content``.
"""

from __future__ import annotations

from mcp_result_wire._format_routing import FormatRoutingMiddleware
from mcp_result_wire._list_view import ListViewMiddleware, ListViewSettings

__all__ = [
    "FormatRoutingMiddleware",
    "ListViewMiddleware",
    "ListViewSettings",
]
