"""The generic MCP steps. Import them into the conftest that collects your features::

    from mcp_steps.steps import *  # noqa: F403

They read the ``mcp_world`` fixture (an :class:`mcp_steps.McpWorld`, usually an
:class:`mcp_steps.McpSessions` or a suite's own world built on one).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pytest_bdd import given, parsers, when

if TYPE_CHECKING:
    from mcp_steps import McpWorld

#: The actors a step can name: the first session, and a second one on the same server.
ACTOR = r"(?P<actor>the agent|someone else)"


@given(parsers.re(ACTOR + r' calls "(?P<tool>[^"]+)" with:'))
@when(parsers.re(ACTOR + r' calls "(?P<tool>[^"]+)" with:'))
def an_actor_calls_a_tool_with(mcp_world: McpWorld, actor: str, tool: str, docstring: str) -> None:
    """The docstring is the tool's own arguments as JSON; a refusal is kept, never raised."""
    mcp_world.call(tool, mcp_world.prepare(tool, json.loads(docstring)), actor=actor)
