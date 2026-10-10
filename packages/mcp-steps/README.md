# mcp-steps

**Stop rewriting the harness that drives an MCP server from Gherkin.** Each actor is its own
MCP session on one server; a tool call keeps its result or its refusal for the `Then` steps.

```python
# conftest.py of the suite
import asyncio
import pytest
from fastmcp import Client
from mcp_steps import McpSessions
from mcp_steps.steps import *  # noqa: F403  — `{actor} calls "{tool}" with:`

@pytest.fixture
def mcp_world():
    with asyncio.Runner() as runner:
        world = McpSessions(runner, connect=lambda actor: Client(build_server()))
        yield world
        world.close()
```

```gherkin
When the agent calls "create" with:
  """
  {"type": "project", "title": "Harbor migration"}
  """
And someone else calls "find" with:
  """
  {"text": "harbor"}
  """
```

## Rules

- **Actors.** `the agent` and `someone else` are two sessions on the same server, opened on
  first use by `connect(actor)`. A suite may open more (an observer that reads without
  touching the outcome) through `session(actor)` and `ask(...)`.
- **One outcome.** `call` sets `last` (the structured value plus `notices`, the text blocks
  after the first) and clears `error`, or sets `error` (the refusal) and clears `last`.
  A refusal is remembered, never raised. `ask` returns both without keeping either.
- **The refusal** is `{"error": …}` from the structured content or from the first text
  block's JSON; plain text becomes `{"message": text}`. Pass `refusal=` to read it another
  way (`a2effect.testing.envelope_of` for an a2effect envelope).
- **Hooks.** Override `prepare(tool, args)` to fill placeholders before a call. A suite whose
  world is its own class only needs `prepare` and `call` (`McpWorld`).
- Steps are synchronous (pytest-bdd runs no async steps); calls run on the `asyncio.Runner`
  you pass. No sibling shelf dependency. The `Then` steps over a result are the suite's own;
  `a2effect.testing.steps` has `the call is refused with "{code}"` over an `outcome` fixture,
  which an `McpSessions` satisfies.
