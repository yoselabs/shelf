"""mcp-arg-errors — a tool call whose arguments do not fit the tool's schema, as a fault an agent can act on.

FastMCP validates a call's arguments before the tool body runs, so a server's own error
handling never sees that failure: it reaches the client as pydantic's text, with no
envelope and no next step. :class:`ArgumentErrorMiddleware` catches it and hands the
consumer an :class:`ArgumentFault` to render in its own error format.

One fault is singled out. A client caches a server's tool list when it connects; when the
server later drops a parameter, the client keeps sending it, often as a default the agent
never chose, and every call fails. An argument the tool does not have is reported as
``unknown``, with a hint to reconnect, so the agent is told how to recover instead of
retrying a call that cannot succeed. The server never accepts the dead argument: that would
be the backward compatibility a schema change exists to end.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from fastmcp.server.middleware import Middleware
from pydantic import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    import mcp.types as mt
    from fastmcp.server.middleware import CallNext, MiddlewareContext
    from fastmcp.tools import ToolResult

#: What a client whose tool list is stale should do. Names Claude Code's command because
#: that is where agents meet it most; any client's "reconnect" does the same.
STALE_TOOL_LIST_HINT = (
    "your client's tool list is older than this server's: reconnect the MCP server to refresh it "
    "(in Claude Code: /mcp), then call again without this argument"
)

#: pydantic's error types for an argument the function does not take.
_UNKNOWN_TYPES = frozenset({"unexpected_keyword_argument", "extra_forbidden"})


@dataclass(frozen=True)
class ArgumentFault:
    """One argument of a tool call that does not fit the tool's schema.

    ``unknown`` is true when the tool has no such argument, which a current client never
    sends; ``message`` and ``hint`` are ready for an agent to read.
    """

    tool: str
    argument: str
    reason: str
    unknown: bool

    @property
    def message(self) -> str:
        if self.unknown:
            return f"{self.tool} has no argument {self.argument!r}"
        return f"{self.argument}: {self.reason}"

    @property
    def hint(self) -> str | None:
        return STALE_TOOL_LIST_HINT if self.unknown else None


def argument_fault(exc: BaseException, tool: str) -> ArgumentFault | None:
    """The fault a schema failure stands for, or ``None`` for any other failure.

    An unknown argument wins over the call's other failures: a stale client's call fails on
    the argument it should not send, and fixing anything else first would not help.
    """
    found: BaseException | None = exc
    while found is not None and not isinstance(found, ValidationError):
        found = found.__cause__ or found.__context__
    if not isinstance(found, ValidationError) or not found.errors():
        return None
    errors = found.errors()
    first = next((e for e in errors if e["type"] in _UNKNOWN_TYPES), errors[0])
    argument = ".".join(str(part) for part in first["loc"]) or "arguments"
    return ArgumentFault(tool=tool, argument=argument, reason=first["msg"], unknown=first["type"] in _UNKNOWN_TYPES)


class ArgumentErrorMiddleware(Middleware):
    """Turn a call's argument-schema failure into the consumer's error result.

    ``to_result`` renders an :class:`ArgumentFault` as the server's own error
    ``ToolResult``; every other failure passes through untouched.
    """

    def __init__(self, to_result: Callable[[ArgumentFault], ToolResult]) -> None:
        self._to_result = to_result

    @override
    async def on_call_tool(
        self, context: MiddlewareContext[mt.CallToolRequestParams], call_next: CallNext[mt.CallToolRequestParams, ToolResult]
    ) -> ToolResult:
        try:
            return await call_next(context)
        except Exception as exc:
            fault = argument_fault(exc, context.message.name)
            if fault is None:
                raise
            return self._to_result(fault)


__all__ = ["STALE_TOOL_LIST_HINT", "ArgumentErrorMiddleware", "ArgumentFault", "argument_fault"]
