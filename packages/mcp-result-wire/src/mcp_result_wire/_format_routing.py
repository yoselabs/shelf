"""Format-routing middleware — compress the MCP ``content`` channel per an encoding plan."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, override

from fastmcp.server.middleware import Middleware
from page_tsv import render_plain

if TYPE_CHECKING:
    from fastmcp.server.middleware import MiddlewareContext
    from page_tsv import EncodingPlan

_log = logging.getLogger(__name__)
_WARN_ONCE: set[str] = set()


class FormatRoutingMiddleware(Middleware):
    """Re-derive the MCP ``content`` channel from a tool's :class:`EncodingPlan`.

    Register before a projection middleware so this post-call processing runs
    *after* any list-view projection — ``content`` is always derived from the
    final ``structured_content``.

    ``plans`` maps a registered tool name to its static ``EncodingPlan``, passed in, never
    sniffed from framework metadata. Install it only for an LLM consumer: a code or machine
    consumer gets the tool results untouched by not having it.

    One behaviour: ``content`` is re-derived, ``structured_content`` stays the complete value.
    A different wire shape (no structured channel, marker-only content) is a different
    middleware, not a switch here (constitution Article IX).
    """

    def __init__(
        self,
        *,
        plans: dict[str, EncodingPlan],
    ) -> None:
        self._plans = plans

    @override
    async def on_call_tool(
        self,
        context: MiddlewareContext[Any],
        call_next: Any,
    ) -> Any:
        result = await call_next(context)

        # Skip when: (a) error result (envelope owns structured_content, set by an
        # error-envelope middleware), or (b) no tool name on context.
        if getattr(result, "is_error", False):
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


__all__ = ["FormatRoutingMiddleware"]
