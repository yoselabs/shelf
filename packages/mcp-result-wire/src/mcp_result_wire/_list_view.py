"""List-view middleware — project fields and paginate list-shaped results.

Generic form: settings are supplied as an explicit ``dict[str, ListViewSettings]``
keyed by tool name (parallel to :class:`FormatRoutingMiddleware`'s ``plans``), so the
middleware never sniffs framework-specific tool metadata. A tool with
``default_fields`` set projects each row of a list result down to those keys; a tool
with ``page_size`` set slices. Single objects, scalars, and non-list results pass
through untouched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

_log = logging.getLogger(__name__)
_WARN_ONCE: set[str] = set()


@dataclass(frozen=True)
class ListViewSettings:
    """Per-tool projection/pagination policy for a list-shaped result."""

    default_fields: tuple[str, ...] = field(default=())
    page_size: int | None = None


def _project_row(row: Any, fields: tuple[str, ...]) -> Any:
    if not isinstance(row, dict):
        return row
    return {k: row[k] for k in fields if k in row}


def _apply_to_items(items: list[Any], settings: ListViewSettings) -> list[Any]:
    if settings.default_fields:
        items = [_project_row(r, settings.default_fields) for r in items]
    if isinstance(settings.page_size, int) and settings.page_size > 0:
        items = items[: settings.page_size]
    return items


def _apply(result: Any, settings: ListViewSettings) -> Any:
    if isinstance(result, list):
        return _apply_to_items(result, settings)
    return result


class ListViewMiddleware(Middleware):
    """Apply per-tool list-view settings to the post-call result.

    ``settings`` maps a registered tool name to its :class:`ListViewSettings`; a tool
    with no entry passes through untouched.
    """

    def __init__(self, settings: dict[str, ListViewSettings]) -> None:
        self._settings = settings

    async def on_call_tool(
        self,
        context: MiddlewareContext[Any],
        call_next: Any,
    ) -> Any:
        result = await call_next(context)

        tool_name = getattr(context.message, "name", None)
        if not tool_name:
            return result
        settings = self._settings.get(tool_name)
        if settings is None:
            return result

        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict) and "result" in structured:
            new_inner = _apply(structured["result"], settings)
            new_structured = {**structured, "result": new_inner}
            try:
                return type(result)(
                    content=result.content,
                    structured_content=new_structured,
                    meta=getattr(result, "meta", None),
                )
            except Exception as exc:  # noqa: BLE001 -- middleware must not raise; degrade observably
                key = f"{tool_name}::project"
                if key not in _WARN_ONCE:
                    _WARN_ONCE.add(key)
                    _log.warning("ListViewMiddleware: result reconstruction failed for %s: %s", tool_name, exc)
                return result

        return result


__all__ = ["ListViewMiddleware", "ListViewSettings"]
