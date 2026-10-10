"""Drive an MCP server from Gherkin steps, synchronously, the way a client sees it.

:class:`McpSessions` holds one ``fastmcp.Client`` per actor, all opened by one ``connect``
factory (so all on the same server), and runs each call on an ``asyncio.Runner``: pytest-bdd
steps are plain functions. A call keeps either its result or its refusal, never both, and a
refusal is remembered, never raised.

The step ``{actor} calls "{tool}" with:`` lives in :mod:`mcp_steps.steps`; it reads the
``mcp_world`` fixture, anything shaped like :class:`McpWorld`.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final, Protocol

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from fastmcp import Client
    from fastmcp.client.client import CallToolResult

__all__ = ["AGENT", "SOMEONE_ELSE", "McpSessions", "McpWorld", "refusal_of", "result_of"]

#: The actor whose session a step uses when it names none.
AGENT: Final = "the agent"
#: A second session on the same server.
SOMEONE_ELSE: Final = "someone else"


class McpWorld(Protocol):
    """What the ``mcp_world`` fixture returns for :mod:`mcp_steps.steps`."""

    def prepare(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """The arguments as the call sends them (a suite fills placeholders here)."""
        ...

    def call(self, tool: str, args: dict[str, Any], actor: str = AGENT) -> Any:
        """Call ``tool`` as ``actor``; keep the result or the refusal."""
        ...


def _text(block: Any) -> str | None:
    text = getattr(block, "text", None)
    return text if isinstance(text, str) else None


def refusal_of(result: CallToolResult) -> dict[str, Any]:
    """The refusal in an error result: ``{"error": …}`` from the structured content or the first
    text block's JSON, or ``{"message": <text>}`` when the server sent plain text."""
    body: Any = result.structured_content
    if not isinstance(body, dict):
        text = _text(result.content[0]) if result.content else None
        try:
            body = json.loads(text) if text is not None else {}
        except json.JSONDecodeError:
            return {"message": text}
    error = body.get("error", body) if isinstance(body, dict) else {"message": str(body)}
    return error if isinstance(error, dict) else {"message": str(error)}


def result_of(result: CallToolResult) -> dict[str, Any]:
    """The structured value of a successful result, plus ``notices``: the text blocks after the first."""
    out: dict[str, Any] = dict(result.structured_content or {})
    out["notices"] = [text for block in result.content[1:] if (text := _text(block)) is not None]
    return out


class McpSessions:
    """One MCP session per actor on one server, called synchronously; the last outcome is kept.

    ``connect(actor)`` returns an unopened ``fastmcp.Client``; it is opened on first use and
    closed by :meth:`close`, last opened first. ``last`` is the last result (``None`` after a
    refusal), ``error`` the last refusal (``None`` after a success).
    """

    def __init__(
        self,
        runner: asyncio.Runner,
        connect: Callable[[str], Client[Any]],
        *,
        refusal: Callable[[CallToolResult], dict[str, Any]] = refusal_of,
    ) -> None:
        self.runner = runner
        self.connect = connect
        self.refusal = refusal
        self.sessions: dict[str, Client[Any]] = {}
        self.last: Any = None
        self.error: dict[str, Any] | None = None

    def session(self, actor: str = AGENT) -> Client[Any]:
        """``actor``'s open session, opened now if it is the first use."""
        if actor not in self.sessions:
            client = self.connect(actor)
            self.runner.run(client.__aenter__())
            self.sessions[actor] = client
        return self.sessions[actor]

    def prepare(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG002 — a hook for a suite
        return args

    def ask(self, tool: str, args: dict[str, Any], actor: str = AGENT) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Call ``tool`` and return ``(result, refusal)`` without keeping either."""
        result = self.runner.run(self.session(actor).call_tool(tool, args, raise_on_error=False))
        if result.is_error:
            return None, self.refusal(result)
        return result_of(result), None

    def call(self, tool: str, args: dict[str, Any], actor: str = AGENT) -> dict[str, Any] | None:
        """Call ``tool`` as ``actor``; the result, or the refusal, becomes the one the steps see."""
        self.last, self.error = self.ask(tool, args, actor)
        return self.last

    def close(self) -> None:
        """Close every session, last opened first."""
        for client in list(self.sessions.values())[::-1]:
            self.runner.run(client.__aexit__(None, None, None))
        self.sessions.clear()
