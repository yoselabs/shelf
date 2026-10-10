"""Every failure of a FastMCP tool call as one error result an agent can act on.

FastMCP masks an exception escaping a tool body before any middleware sees it: the
middleware gets a generic ``ToolError`` and the original is gone. So the conversion
happens at the tool boundary. :meth:`ErrorWire.guard` wraps a tool function; whatever it
raises comes back as an ``is_error`` :class:`~fastmcp.tools.ToolResult` whose
``structured_content`` is ``{"error": <envelope>}`` and whose text is rendered from the
same envelope, so the two channels cannot disagree. FastMCP returns a ``ToolResult`` from a
tool function as is.

A typed error is anything with a ``kind`` and ``to_envelope_dict()`` (an ``a2effect``
``AppError`` is one); it renders as itself. Anything else is a defect: it is logged with a
trace id, and the caller gets the consumer's defect error carrying only that id, never
the original exception's text. A typed error of kind ``bug`` is logged the same way and
keeps its own envelope with the trace id added, so the log line and the envelope point at
each other.

Paired with :class:`~mcp_arg_errors.ArgumentErrorMiddleware` for the failures FastMCP
raises before the body runs: render an :class:`~mcp_arg_errors.ArgumentFault` as a typed
error and hand it to :meth:`ErrorWire.result`.
"""

from __future__ import annotations

import functools
import inspect
import json
import logging
import uuid
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, runtime_checkable

from fastmcp.tools import ToolResult

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

#: The most of ``details`` an error's text carries; the envelope keeps them whole.
DETAILS_CHARS = 2_000

_LOG = logging.getLogger(__name__)


@runtime_checkable
class TypedError(Protocol):
    """An error that knows its wire form: an ``a2effect.AppError``, or anything shaped so."""

    kind: ClassVar[str]

    def to_envelope_dict(self) -> dict[str, Any]: ...


def envelope_text(envelope: Mapping[str, Any], *, details_chars: int = DETAILS_CHARS) -> str:
    """What an agent reads of an error: the message, the hint, and the details as JSON.

    Some clients show only the text of a failed call and drop ``structured_content``, so
    the details have to be in the text too. Long details are cut here, never in the
    envelope.
    """
    lines = [str(envelope["message"])]
    if envelope.get("hint"):
        lines.append(f"Hint: {envelope['hint']}")
    if envelope.get("details"):
        details = json.dumps(envelope["details"], ensure_ascii=False, default=str, separators=(",", ":"))
        if len(details) > details_chars:
            details = details[:details_chars] + "… (cut; the structured error holds all of it)"
        lines.append(f"Details: {details}")
    return "\n".join(lines)


def _envelope_only(_error: TypedError, envelope: Mapping[str, Any]) -> str:
    return envelope_text(envelope)


def _fresh_trace_id(_exc: BaseException) -> str:
    return str(uuid.uuid4())


class ErrorWire:
    """Turns whatever a tool raised into the error result.

    ``defect`` builds the typed error an untyped failure becomes, from a message naming
    the trace id (``a2effect.UnexpectedDefect``). ``trace_id`` reads the id a failure was
    stamped with (default: a fresh one). ``text`` renders the result's text from the typed
    error and its envelope (default :func:`envelope_text`). ``passthrough`` exception types
    are re-raised untouched, for a failure the author already shaped for the wire.
    """

    def __init__(
        self,
        defect: Callable[[str], TypedError],
        *,
        trace_id: Callable[[BaseException], str] = _fresh_trace_id,
        text: Callable[[TypedError, Mapping[str, Any]], str] = _envelope_only,
        passthrough: tuple[type[BaseException], ...] = (),
        logger: logging.Logger | None = None,
    ) -> None:
        self._defect = defect
        self._trace_id = trace_id
        self._text = text
        self._passthrough = passthrough
        self._log = logger or _LOG

    def result(self, exc: Exception) -> ToolResult:
        """``exc`` as an ``is_error`` result: text plus ``{"error": envelope}``."""
        if isinstance(exc, TypedError) and exc.kind != "bug":
            typed: TypedError = exc
            envelope = exc.to_envelope_dict()
        else:
            trace_id = self._trace_id(exc)
            self._log.error("internal_error trace_id=%s", trace_id, exc_info=exc)
            typed = exc if isinstance(exc, TypedError) else self._defect(f"internal error; trace_id={trace_id}")
            envelope = typed.to_envelope_dict()
            envelope["details"] = {**(envelope.get("details") or {}), "trace_id": trace_id}
        return ToolResult(content=self._text(typed, envelope), structured_content={"error": envelope}, is_error=True)

    def guard(self, fn: Callable[..., Any], *, drop_params: frozenset[str] = frozenset()) -> Callable[..., Any]:
        """Wrap an async tool function so every failure leaves as :meth:`result`.

        The wrapper advertises ``fn``'s signature (FastMCP builds the schema from it),
        minus ``drop_params``: a parameter dropped here is absent from the schema on this
        binding, and stripped from the call too, so it does not rest on schema validation
        alone.
        """

        @functools.wraps(fn)
        async def _guarded(**kwargs: Any) -> Any:
            for name in drop_params:
                kwargs.pop(name, None)
            try:
                return await fn(**kwargs)
            except self._passthrough:
                raise
            except Exception as exc:  # noqa: BLE001 — the boundary: every failure leaves as an error result
                return self.result(exc)

        sig = inspect.signature(fn)
        if drop_params:
            sig = sig.replace(parameters=[p for name, p in sig.parameters.items() if name not in drop_params])
        setattr(_guarded, "__signature__", sig)  # noqa: B010 — PEP 362's introspection target, read by FastMCP
        return _guarded


__all__ = ["DETAILS_CHARS", "ErrorWire", "TypedError", "envelope_text"]
