# MCP server conventions

Framework layer on top of [python.md](python.md) for a Python MCP server built on the standalone `fastmcp`
package. Every Python rule applies. `{{mcp_root}}` is the folder holding the `pyproject.toml` that declares `fastmcp`.

## Tools per role

| role | tool | enforced by |
|---|---|---|
| framework-version | `fastmcp` in `[project].dependencies` with a lower bound and a major cap, locked in `uv.lock`; one test asserts the negotiated protocol version | config check, test |
| project-hygiene | no `print()` in server code (ruff `T20`); logs go to stderr; stdout carries only JSON-RPC | ruff, stdio test |
| build | stdio smoke test: real subprocess, handshake, list tools, one call, one bad call | gate (`pytest`) |
| tests | in-memory `Client(server)` contract tests; Gherkin through `mcp-steps` where steps are shared | gate (`pytest`) |
| surface-integrity | the tool list is a committed snapshot; property tests over the live list (description, annotations, schema) | gate (`pytest`) |
| architecture | the core does not import `fastmcp`; the server module is a thin adapter | untested (python-uv architecture tool open) |
| binary-assets, embedded-script-lint, ci, hooks | not applicable | - |

## Run

```bash
just check                          # includes the contract and stdio tests
uv run pytest tests/contracts -q    # the tool-list snapshot and property tests
uv run fastmcp inspect <file.py>:mcp --format mcp   # what a client would see, as JSON
```

## Rules

| rule | why |
|---|---|
| Never write to stdout from server code; log to stderr | Over stdio, stdout holds only protocol messages; one stray line breaks the session |
| Every tool sets all four annotations: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` | FastMCP's defaults are the pessimistic ones (not read-only, destructive, open-world); clients treat annotations as hints from this server only |
| A read tool is `readOnlyHint=True`, `destructiveHint=False`; a tool that deletes or overwrites is `destructiveHint=True` | Clients ask the human before destructive calls |
| The tool description is for a model: what it does, when to use it, what each argument means, what comes back, what it does not do | The description is the only documentation an agent reads |
| Argument names say what the value is (`user_id`, not `user`); enums over free strings where the set is closed | Models pick wrong values for vague names |
| Inputs are typed (pydantic model or annotated parameters); never hand-write `inputSchema` | The schema is generated from the signature so the two cannot drift |
| Return a model, dataclass or dict so `outputSchema` and `structuredContent` are generated; keep the text content short | Clients and models parse the structure; the text spends context |
| Failures are results with `is_error=True` and an actionable message (what was wrong, what a valid call looks like), never a traceback and never a masked "Error calling tool" | The model reads the error and retries; protocol errors it mostly cannot fix |
| Bound every list: a default limit, a cursor or range, and a note in the result when truncated | One unbounded result fills the agent's context |
| Tool names are stable, snake_case, 1-128 chars of `[A-Za-z0-9_.-]`, and a description never names a tool that does not exist | Renames break prompts; a description pointing at a missing tool sends the agent after it |
| Change a description or schema on purpose: run the snapshot update, read the diff, commit both | The snapshot is the public contract; description wording changes agent behavior |
| Secrets (tokens, keys) come from the environment or a secret store, never from tool arguments or tool output | Tool arguments and results enter the model's context |
| An HTTP server validates `Origin`, binds `127.0.0.1` unless told otherwise, and requires auth on every non-local connection | Spec requirement for Streamable HTTP; DNS rebinding reaches local servers |

## Layout

| thing | where |
|---|---|
| Server object, tool registration, error mapping, annotations | one module (`<pkg>/mcp/server.py`): an adapter, no domain rules |
| Domain logic | the core package, importable and testable without `fastmcp` |
| Contract tests, snapshot | `tests/contracts/` (`test_tool_list.py`, `<name>.snapshot.json`) |
| Stdio smoke test | `tests/test_stdio_serves.py` |

## Traps

- FastMCP 4 dumps `ToolAnnotations` in snake_case unless you pass `by_alias=True`; FastMCP 3 does not care. Dump the snapshot with `model_dump(mode="json", by_alias=True, exclude_none=True)` so it reads as the wire does. A 3 to 4 bump adds a `title` field to every tool in the snapshot.
- `strict_input_validation` is off by default: `"10"` is coerced to `10`. Decide on purpose; the contract test for a wrong argument type must match the choice.
- The official SDK renamed its server class: `mcp.server.fastmcp` is removed in `mcp` 2.x (`MCPServer` instead). Depend on `fastmcp`, not on the SDK's server class; import `mcp.types` only when you need a content type.
- A tool body exception is masked by FastMCP before middleware sees it. Convert at the tool boundary (`ToolError`, or the shelf's `mcp-arg-errors` `ErrorWire.guard`), or the model gets a generic message.
- Sync tools run in a thread pool in FastMCP 3 and later; do not rely on being on the event loop.
- A banner or `rich` console on stdout breaks stdio. FastMCP writes its own to stderr; yours must too.
- Tools list order should be deterministic (newer protocol revisions say SHOULD): register in a fixed order and sort in the snapshot.
- `fastmcp`'s major and the `mcp` SDK's major move together (FastMCP 4 runs on `mcp` 2.x; FastMCP 3 on `mcp` 1.x). Never pin them apart.
