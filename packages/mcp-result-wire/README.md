# mcp-result-wire

FastMCP result middleware for token-lean, projected tool output. Two middlewares,
both driven by **explicit per-tool registries** (never sniffed from framework tool
metadata), composing [`page-tsv`](../page-tsv) for the encoding.

## `FormatRoutingMiddleware(plans, consumer, ...)`

Re-derives a tool's `content` channel from its `EncodingPlan` (TSV / page-tsv /
envelope) for the `llm` consumer, leaving `structured_content` canonical. `code` /
`machine` consumers pass through untouched.

```python
from mcp_result_wire import FormatRoutingMiddleware
from page_tsv import EncodingPlan

server.add_middleware(FormatRoutingMiddleware(
    plans={"search": EncodingPlan("page-tsv")},
    consumer="llm",
))
```

`compact` (drop `structuredContent` for non-conformant clients) and
`structured_output` (keep structured, replace `content` with a marker) are optional
wire modes.

## `ListViewMiddleware(settings)`

Projects list rows to `default_fields` and paginates to `page_size`.

```python
from mcp_result_wire import ListViewMiddleware, ListViewSettings

server.add_middleware(ListViewMiddleware({
    "list_tasks": ListViewSettings(default_fields=("id", "title"), page_size=50),
}))
```

## Ordering

Register `FormatRoutingMiddleware` **outermost** (before `ListViewMiddleware`) so the
`content` channel is derived from the already-projected `structured_content`.

## Composition

Built on [`page-tsv`](../page-tsv) (the encoding) and `fastmcp` (the middleware base).

## Sharp edges around FastMCP and the MCP SDK

Each of these cost a consumer a real outage. None is a FastMCP bug you could have
read about beforehand.

- **fastmcp 3.3.x cannot build an error result.** `ToolResult(is_error=True)`
  raises `TypeError` before 3.4, so every typed-error response crashed. It
  compounded: the failing call was holding a write lock, so the *next* write
  wedged too (a2kay 6b07d33, found only because a lock resolved to 3.3.1). This
  package requires `fastmcp>=3.4` so a consumer cannot resolve the broken version
  through it.
- **A streamable-http handshake can hang forever under a burst.** With many
  concurrent sessions opening at once, the client's `__aenter__` can wait for a
  reply that never comes. Retrying on the same event loop does not recover it.
  Bound each attempt (`asyncio.wait_for`), and on timeout abandon that loop *and*
  that client, then retry on a fresh loop. In a2kay this hang took down the whole
  test suite.
- **A parameter named `type`, `id` or `format` shadows a builtin.** Name it
  `type_` in Python and give it a wire alias (`Field(alias="type")`). If the
  Python name reaches the schema, the server advertises `type_` while every LLM
  caller sends `type`, and every call fails validation. Pin it with a test that
  reads the tool's input schema.
- **`initialize` has a deadline, and cold start counts against it.** Clients give
  the handshake about 30s. Work done before the server answers (a2kay re-derived
  every entity's links on boot) grows with the data, and past ~250 entities the
  client could no longer connect at all. Do O(data) work after serving, or
  incrementally.

Checked and **not** true on fastmcp 3.4.4, though consumer notes once said so:
`functools.wraps` alone does give the wrapped function's schema; set
`__signature__` only to *change* what is advertised. A parameter removed from the
advertised signature is rejected when a caller sends it anyway.
