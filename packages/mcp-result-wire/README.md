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
