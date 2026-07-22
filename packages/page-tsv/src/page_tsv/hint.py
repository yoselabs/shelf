"""The ``format_hint`` adapter — a thin hint-vocabulary shim over ``render``.

``format_response`` lets callers that speak the legacy ``format_hint`` vocabulary
(``auto`` / ``json`` / ``tsv`` / ``page-tsv``) reach the consumer-aware
:func:`render` seam.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from page_tsv.inference import EncodingPlan
from page_tsv.render import render
from page_tsv.response import Page, Response

if TYPE_CHECKING:
    from page_tsv.formats import FormatHint


def _plan_for_hint(format_hint: FormatHint) -> EncodingPlan:
    """Map the legacy ``format_hint`` vocabulary to an :class:`EncodingPlan`."""
    if format_hint == "tsv":
        return EncodingPlan("tsv")
    if format_hint == "page-tsv":
        return EncodingPlan("page-tsv")
    # "auto" and "json" both encode JSON when called outside a tool dispatch.
    return EncodingPlan("json")


def format_response(raw: Any, *, format_hint: FormatHint = "auto") -> Response:
    """Encode ``raw`` per ``format_hint`` and return a :class:`Response`.

    A thin ``format_hint``-shaped adapter over :func:`render` for callers that still
    speak the hint vocabulary (``auto`` / ``json`` / ``tsv`` / ``page-tsv``).
    """
    if format_hint == "page-tsv" and not isinstance(raw, Page):
        msg = f"format_hint='page-tsv' requires a Page instance, got {type(raw).__name__}"
        raise TypeError(msg)

    rendered = render(raw, "llm", plan=_plan_for_hint(format_hint))
    return Response(data=rendered.text, format=rendered.format)


__all__ = ["format_response"]
