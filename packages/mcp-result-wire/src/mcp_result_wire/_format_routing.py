"""Format-routing middleware — compress the MCP ``content`` channel per an encoding plan."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastmcp.server.middleware import Middleware
from mcp.types import TextContent
from page_tsv import render_plain

if TYPE_CHECKING:
    from fastmcp.server.middleware import MiddlewareContext
    from page_tsv import Consumer, EncodingPlan

_log = logging.getLogger(__name__)
_WARN_ONCE: set[str] = set()


class FormatRoutingMiddleware(Middleware):
    """Re-derive the MCP ``content`` channel from a tool's :class:`EncodingPlan`.

    Register before a projection middleware so this post-call processing runs
    *after* any list-view projection — ``content`` is always derived from the
    final ``structured_content``.

    ``plans`` maps a registered tool name to its static ``EncodingPlan``; ``consumer``
    (``"llm"`` / ``"code"`` / ``"machine"``) is a caller parameter — only the ``llm``
    tier compresses. Both are passed in, never sniffed from framework metadata.
    """

    def __init__(
        self,
        *,
        plans: dict[str, EncodingPlan],
        consumer: Consumer,
        compact: bool = False,
        structured_output: bool = False,
    ) -> None:
        self._plans = plans
        self._consumer: Consumer = consumer
        self._compact = compact
        # When True, the success-path wire keeps ``structured_content`` (full payload)
        # and replaces ``content[].text`` with a short marker — saves duplicate JSON on
        # hosts that forward structuredContent to the model.
        self._structured_output = structured_output

    async def on_call_tool(  # noqa: PLR0911 -- three mutually exclusive wire modes (dual / compact / strict) + early-exit guards
        self,
        context: MiddlewareContext[Any],
        call_next: Any,
    ) -> Any:
        result = await call_next(context)

        # Skip when: (a) error result (envelope owns structured_content, set by an
        # error-envelope middleware), (b) consumer is not the compressing ``llm`` tier,
        # or (c) no tool name on context.
        if getattr(result, "is_error", False) or self._consumer != "llm":
            return result
        tool_name = getattr(context.message, "name", None)
        if not tool_name:
            return result

        plan = self._plans.get(tool_name)
        structured = getattr(result, "structured_content", None)

        try:
            # Re-derive the compressed ``content`` for a tabular result.
            new_content: Any = None
            if plan is not None and plan.kind != "json" and isinstance(structured, dict):
                if plan.kind == "tsv":
                    if "result" in structured:
                        new_content = render_plain(structured["result"], plan)
                else:  # page-tsv / envelope — the BaseModel envelope itself
                    new_content = render_plain(structured, plan)

            if self._compact:
                # Drop ``structuredContent`` entirely for non-conformant MCP clients
                # that mishandle dual channels.
                content = new_content if new_content is not None else result.content
                return type(result)(
                    content=content,
                    structured_content=None,
                    meta=getattr(result, "meta", None),
                )

            if self._structured_output and structured is not None:
                # Strict mode: keep structured_content; replace content[].text with a
                # short marker. Saves ~50% success tokens on hosts that forward
                # structuredContent; degrades hosts that don't.
                marker = _short_marker(structured)
                return type(result)(
                    content=[TextContent(type="text", text=marker)],
                    structured_content=structured,
                    meta=getattr(result, "meta", None),
                )

            if new_content is None:
                # Nothing tabular to recompress — both channels already fine.
                return result
            return type(result)(
                content=new_content,
                structured_content=structured,
                meta=getattr(result, "meta", None),
            )
        except Exception as exc:  # noqa: BLE001 -- middleware must not raise; degrade observably
            key = f"{tool_name}::format-routing"
            if key not in _WARN_ONCE:
                _WARN_ONCE.add(key)
                _log.warning(
                    "FormatRoutingMiddleware: content re-derivation failed for %s: %s",
                    tool_name,
                    exc,
                )
            return result


def _short_marker(structured: Any) -> str:
    """Return a short type-identifying marker for strict structured-output mode.

    For ``{"result": [...]}`` shapes (lists), report the item count. For
    ``{"result": {...}}`` shapes (single model), report the ``_type`` discriminator if
    present, else ``"structured"``. Otherwise emit a static placeholder.
    """
    if isinstance(structured, dict):
        inner = structured.get("result", structured)
        if isinstance(inner, list):
            return f"[{len(inner)} item(s)]"
        if isinstance(inner, dict):
            type_hint = inner.get("_type") or inner.get("type")
            if isinstance(type_hint, str) and type_hint:
                return f"<{type_hint}>"
    return "(see structuredContent)"


__all__ = ["FormatRoutingMiddleware"]
