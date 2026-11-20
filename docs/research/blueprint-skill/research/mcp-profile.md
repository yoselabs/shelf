# Research: blueprint framework profile for Python MCP servers (shelf-4sv)

Date: 2026-10-11. Labels: **tested** = I ran it here (scratch venvs under `sdk/`, or the real blueprint judge against a2kay, read-only);
**read** = read in a primary source or a2kay file; **untested** = taken from a secondary source or memory.

## 1. Version facts

| fact | label | source |
|---|---|---|
| `fastmcp` on PyPI: 2.14.0 (2025-12-11), 3.0.0 (2026-02-18), 4.0.0 (2026-08-31), 4.1.0 current (2026-10-08); 3.4.8 still released 2026-10-04; last 2.x is 2.14.7 | tested (PyPI JSON) | pypi.org/pypi/fastmcp/json |
| `mcp` (official SDK): 1.0.0 (2024-11), 2.0.0 (2026-07-28), 2.3.0 current (2026-10-02), 1.30.0 last seen 1.x (2026-09-07) | tested (PyPI JSON) | pypi.org/pypi/mcp/json |
| fastmcp 3.4.x requires `mcp>=1.24,<2`; fastmcp 4.1.0 requires `fastmcp-slim==4.1.0`, runs on `mcp` 2.3.0 (`pip` output: `"mcp": "2.3.0"` in `fastmcp inspect`) and needs pydantic >= 2.12 | tested + read | a2kay `.venv` METADATA; scratch install; gofastmcp.com/getting-started/upgrading/from-fastmcp-3 |
| In `mcp` 2.x, `mcp.server.fastmcp` is **removed**: importing it raises ModuleNotFoundError telling you FastMCP was renamed `MCPServer` (`from mcp.server.mcpserver import MCPServer`) or to pin `mcp<2` | tested | scratch venv, mcp 2.3.0 |
| `mcp` 2.x `LATEST_PROTOCOL_VERSION` is `2026-07-28`; a2kay's `mcp` 1.28.1 says `2025-11-25` | tested | `mcp.types` in both |
| A FastMCP 4.1.0 server still negotiates `2025-11-25` with a client that asks for it (initialize over stdio returned protocolVersion 2025-11-25) | tested | scratch stdio call |
| FastMCP 3.0 (Feb 2026): provider/transform model, component versioning, session state, per-component auth. 4.0: removes `as_proxy`, `import_server`, `ctx.sample`, `serializer=`, tasks move to an extension; resource-not-found code -32602; httpx2 | read | gofastmcp.com/getting-started/upgrading/from-fastmcp-2 and -from-fastmcp-3 |
| `fastmcp` CLI has `inspect` (text, `--format fastmcp` or `--format mcp` JSON), `list`, `call`, `dev`, `run`, `install`, `generate-cli`; `inspect <file.py> --format mcp` printed tools with inputSchema | tested | fastmcp 4.1.0 scratch run; a2kay `.venv/bin/fastmcp --help` (3.4.4) |

### Which to prescribe

Prescribe the **standalone `fastmcp` package** (PrefectHQ), with a lower bound and a major cap (`fastmcp>=3.4,<4` is a2kay's shape).

Why:
- It is the library the shelf's packages target (`mcp-feedback`, `mcp-result-wire`, `mcp-arg-errors`, `mcp-steps`, `mcp-bridge` all import `fastmcp`). A server on the SDK's own class cannot use them.
- It carries what a strict server needs that the SDK class lacks or changed under it: middleware, `ToolError` plus `mask_error_details`, in-memory `Client(server)`, `fastmcp inspect`, per-component auth.
- `mcp.server.fastmcp` (SDK v1) is a frozen copy and is gone in SDK 2.x; building on it is building on a module with a removal date.

The profile does **not** prescribe the major. Facts: 4.1.0 is current (five weeks old, 4.0.0 on 2026-08-31), it rides SDK 2.x and httpx2 and removed several APIs; 3.4.8 is current on the 3 line and a2kay (the only consumer) is on it. A new server starts on the current major; an existing one stays until the shelf's FastMCP packages say they support 4 (untested: I did not run mcp-feedback / mcp-result-wire against 4.x). The checkable rule is "a lower bound and a cap exist", not the number.

Both 3.4.8 and 4.1.0 passed the same in-memory contract pattern (list tools, annotations present, outputSchema generated from a pydantic return type, bad argument gives `is_error=True` with a pydantic message naming the argument) — **tested**. One difference found: 4.1.0 dumps `ToolAnnotations` in snake_case unless `by_alias=True`, and adds a `title` to every tool; 3.4.8 dumps camelCase either way. A snapshot written with `by_alias=True` reads as the wire does on both.

## 2. Per-role findings

The 11 `FRAMEWORK_ROLES` are Godot-shaped. They fit with remapping; no new role is needed (see 7 for the one gap).

| role | MCP answer | checkable from files / gate | needs judgement |
|---|---|---|---|
| engine-version | `fastmcp` pinned with lower bound and major cap, lock committed; protocol version asserted by one test via `client.initialize_result` | pyproject substring (`fastmcp>=`/`==`/`~=`), `uv.lock` has the name, a test mentions `initialize_result`. The cap `<N` is not checkable with substring `contains` | whether the cap is right |
| project-hygiene | stdout is the protocol: no `print`, logs to stderr (spec: server MUST NOT write non-MCP data to stdout; MAY log to stderr) | ruff `T20` selected (substring in pyproject); stdio test proves the stream | `sys.stdout.write`, third-party libs that print: only the stdio test catches them |
| assets | na | - | - |
| scripts-lint | na | - | - |
| build | real subprocess over stdio: handshake, list, call, bad call (a2kay `tests/test_serve_stdio_e2e.py`, **read**) | a test file containing `StdioTransport`; gate `pytest` | that the test starts the *shipped* entrypoint, not a test double |
| tests | in-memory `Client(server)` contract tests; error result shape | test file with `Client(` and `is_error`; gate `pytest` | coverage of every tool |
| scene-integrity (here: tool-surface integrity) | committed snapshot of `list_tools` wire JSON; properties over the live list | `*.snapshot.json` under tests, a test with `list_tools` and an annotation name | snapshot semantics are only as good as the dump; review of description wording |
| architecture | core never imports `fastmcp`; server module is an adapter | not yet: python-uv architecture tool open | - |
| ci | na (gate already runs the tests) | - | - |
| hooks | na | - | - |
| agent-guidance | `docs/agents/mcp.md` linked from AGENTS.md | file + link | quality of content |

### Concerns from the task list, where each landed

| concern | where | deterministic? |
|---|---|---|
| contract tests via in-memory client | tests | yes (presence); coverage no |
| tool schema snapshot / drift | scene-integrity | yes: a2kay's `test_the_tool_list_is_the_committed_snapshot` diffs on any change (**read**) |
| MCP Inspector / `mcp` CLI validation | refused as a gate step, see 4 | - |
| structured output schemas | tests + rules: return a model so `outputSchema` is generated (**tested**: pydantic return gave `output_schema`). a2kay chooses the opposite, no output schema, to keep its list under 12 KB (**read**, `tests/contracts/test_mcp_tool_list.py`) | presence of a schema: property test; whether it should exist: judgement. The profile must not mandate it. |
| error shape | tests: bad-argument call returns `is_error` with the argument named (**tested** both majors). Spec: input validation errors are tool execution errors with `isError: true` so a model can retry; protocol errors are for unknown tools and malformed requests (**read**, 2025-11-25 tools page). Shelf `mcp-arg-errors` makes the envelope one shape | yes for shape; message quality no |
| auth | architecture/rules: HTTP requires Origin validation, localhost bind, auth on every connection (spec MUST/SHOULD, **read**, 2025-11-25 transports). FastMCP 3 adds per-component auth (**read**) | not from files: depends on transport used. Check only if an HTTP transport is declared; no way to detect with substring today |
| transport config | build row: stdio test, HTTP test over loopback if served | presence of test; config values no |
| protocol-version pinning | engine-version: the server cannot choose the version (the SDK negotiates); pin the library and assert the negotiated string in one test | yes (test mentions `initialize_result`); value no |
| logging to stderr | project-hygiene | partly (T20 + stdio test) |
| resource / prompt naming | rules only. Spec tool-name rule: SHOULD be 1-128 chars from `[A-Za-z0-9_.-]`, unique, case-sensitive (**read**). No spec rule for resource URIs beyond RFC 3986 | tool names: property test in the snapshot test; resources: judgement |
| tool annotations | scene-integrity: all four hints set explicitly. FastMCP defaults are readOnly false, destructive true, idempotent false, openWorld true (**read**, gofastmcp.com/servers/tools). a2kay asserts a (readOnly, destructive, idempotent) triple per tool (**read**) | yes (property test over the live list); correctness of the values is judgement. Spec: clients MUST treat annotations as untrusted unless from a trusted server (**read**) |
| agent-facing conventions | mcp.md rules. Anthropic "Writing tools for agents" (2025-09-11, **read**): few targeted tools, search over list-all, describe like briefing a new hire, unambiguous parameter names (`user_id`), concise vs detailed response option, actionable errors with example input, pagination with sensible defaults (Claude Code caps a tool response at 25,000 tokens by default), annotations for destructive and open-world | presence of non-empty description, size budget, no dangling tool names in descriptions: yes. "Is the description good": no (judge with an eval, not a check) |
| tool-list order and size | a2kay budget 12,288 B (**read**). 2026-07-28 spec: tools/list SHOULD be deterministic in order (**read**) | yes (sorted snapshot, size budget) |

## 3. Deterministic checks (what a check would read)

Works today with the existing `config` / `gate` mechanism (dry-run against a2kay, **tested**, see 6):
- `pyproject.toml` substrings: `fastmcp>=`, `T20`.
- `uv.lock` substring `name = "fastmcp"`.
- `tests/*.py` and `tests/*/*.py` substrings: `initialize_result`, `StdioTransport`, `Client(`, `is_error`, `list_tools`, `readOnlyHint`/`read_only_hint`.
- `tests/**/*.snapshot.json` existence (globs up to three levels, no `**`).
- gate substring `pytest` reachable from `make check`.
- `docs/agents/mcp.md` and its link.

Cannot be done with the current mechanism (engine requests, not part of this draft):
- A regex or "major cap present" check on the fastmcp specifier (`contains` is a substring).
- Reading the snapshot content (is every tool annotated, is every `additionalProperties` false). Today only the repo's own test can do this; the profile checks that such a test exists, not that it is meaningful. A weak spot: substring presence is gameable (a test file that mentions `is_error` in a comment passes).
- Detection from a dependency (section 5).
- Per-tool judgement: description quality, annotation correctness, whether a tool should exist.

## 4. Refused or deferred options

| option | verdict | reason |
|---|---|---|
| Official SDK server class as the prescribed base (`mcp.server.fastmcp` in SDK v1, `MCPServer` in v2) | refused | v1 module removed in SDK 2.x (**tested**); shelf's MCP packages target `fastmcp`; v2 `MCPServer` unproven here |
| MCP Inspector (`npx @modelcontextprotocol/inspector --cli`) as a gate step | refused for now | Node toolchain in a Python gate; fetches over network; v2 in development, no release listed on the repo page (**read**, github.com/modelcontextprotocol/inspector); the in-memory client plus `fastmcp inspect` give the same facts in-process. Keep as a manual debugging tool in mcp.md only if the owner wants it; flagged **untested** (I did not run it) |
| `fastmcp inspect` as the snapshot source | deferred | works (**tested**) but needs a file spec and is a subprocess; the in-memory `list_tools()` dump is faster and a2kay already uses it |
| `fastmcp dev` | refused as a check | interactive debugging UI, not a gate |
| Mandating `outputSchema` on every tool | refused | a2kay measured it at 13,387 of 23,411 bytes of its tool list and removed it deliberately (**read**); a per-repo choice recorded in the snapshot test |
| Mandating Gherkin for MCP tests | refused | same finding as the shelf's pilot: use `mcp-steps` only where steps are shared; plain pytest for the rest (AGENTS.md convention, **read**) |
| FastMCP 2.x | refused | 2.14.7 is last, superseded by two majors; no reason to start there |
| Prescribing the FastMCP major | deferred | see 1: prescribe the cap, not the number |
| A separate `mcp-protocol-conformance` check against an external suite | untested | I did not find or run a conformance suite; if one exists it belongs in the gate (open question for the owner) |
| Servers via `FastMCP.from_openapi` / `from_fastapi` / proxies | out of scope | those generate tools from another spec; the snapshot rule still applies but the "never hand-write inputSchema" rule is moot. Not studied |
| New role names in `FRAMEWORK_ROLES` | deferred | see 7 |

## 5. Detection rule (proposal; needs an engine change)

Current `detect_frameworks` is marker-file only (`FRAMEWORK_MARKERS = {"godot": "project.godot"}`). Proposed second table in `profile.py`:

```python
# A framework is also found by a dependency in pyproject.toml, confirmed by a use in the source.
FRAMEWORK_DEPS = {"mcp": DepRule(deps=("fastmcp", "fastmcp-slim"), used=("FastMCP(",))}
```

Rule, in order:
1. Parse `pyproject.toml` in the repo root and each uv workspace member (three levels, like `walk`). Normalize names (PEP 503: lowercase, `_`/`.` to `-`) from `[project].dependencies` and `[project.optional-dependencies]`. **Not** `[dependency-groups]`: a dev-only dependency is a test client, not a server.
2. Hit when `fastmcp` or `fastmcp-slim` is declared **and** a `.py` file under that project's source contains `FastMCP(` (or a `@<name>.tool` decorator). Reason for step 2: `fastmcp` is also a *client* library (a2web-style callers use `Client`); a client-only repo has no MCP surface to judge. A2kay hits both.
3. The framework folder is the directory of that `pyproject.toml` (`{root}`).
4. The official SDK alone does not trigger: `mcp` in dependencies with `mcp.server.fastmcp` or `MCPServer(` in source is a server, but it is not the profile's base (section 1); report it as `blueprint lacks`-style finding "built on the SDK server class, profile prescribes fastmcp" instead of silently skipping. Open: whether to treat it as the same framework with a failing engine-version row. I lean to the same framework: the failing row is the useful output.
5. Override: `[profile.frameworks] mcp = "."` in `docs/blueprint/blueprint.toml` already works (declared wins, `detect()` line).

Name: the bead says `framework/fastmcp`; I used `mcp` (file `mcp.toml`, `stack = "mcp"`) because most rows are protocol-level and survive a library change. Owner call; renaming is one file name and one dict key.

Dry run (**tested**): I loaded the draft with the real `load_profiles` and `judge_role` against `~/Workspaces/a2kay` read-only:
engine-version pass, project-hygiene pass, build pass, tests pass, scene-integrity pass, architecture untested, assets/scripts-lint/ci/hooks na, agent-guidance not-set-up (a2kay has no `docs/agents/mcp.md`). That the "pass" results are weak evidence is the point of the substring caveat in 3.

## 6. Test carrier pattern in the shelf (**read**)

- `mcp-steps`: Gherkin steps over `McpSessions`, each actor its own `fastmcp.Client` session on one server.
- `mcp-arg-errors`: `ErrorWire.guard` plus `ArgumentErrorMiddleware`, one error envelope for body failures and schema failures.
- `mcp-bridge`, `mcp-feedback`, `mcp-result-wire`, `mcp-clients`: server-side or client-side helpers, all `fastmcp`.
- a2kay carriers: `tests/test_fastmcp_server.py` (in-memory `Client(server)`, frozen tool set, description checks), `tests/contracts/test_mcp_tool_list.py` + `mcp_tool_list.snapshot.json` (snapshot, annotation triples, size budget, regenerate via env var), `tests/test_serve_stdio_e2e.py` (real stdio subprocess), `tests/mcp/test_unknown_argument.py`, `test_error_text_carries_details.py`, `test_every_error_is_catalogued.py`.
- FastMCP's own testing page: in-memory `Client`, pytest-asyncio with `asyncio_mode = "auto"`, inline-snapshot, dirty-equals, parametrize (**read**). a2kay uses `asyncio.run(...)` inside plain pytest functions, so pytest-asyncio is not required; the profile does not mandate either.

## 7. Open questions for the owner

1. Name: `mcp` or `fastmcp`.
2. Engine changes: dependency-based detection (section 5); an optional `regex` key in `config` specs (to check the version cap and to read snapshot files meaningfully).
3. The 2026-07-28 protocol revision (stateless, no `initialize`, `server/discover`, `Mcp-Session-Id` removed, `ttlMs`/`cacheScope` on list results, Logging and Sampling deprecated, log to stderr instead) is real and `mcp` 2.x implements it (**read**, spec changelog; **tested** that SDK 2.3.0 reports it as latest). Not studied: how FastMCP 4's `Client` negotiates it, and what a 2026-07-28 server must additionally assert. The `engine-version` test that asserts the negotiated string will go red on the first bump; that is its job, but the rows say nothing yet about stateless-mode obligations (**untested**).
4. Is a missing role worth adding to `FRAMEWORK_ROLES`? The tool-surface contract is the center of MCP quality and sits under the Godot-named `scene-integrity`. Renaming that role to something neutral ("surface-integrity") would help both profiles; deferred as an engine decision.
5. Conformance suite / Inspector in the gate: not run; decide after a manual look.
6. FastMCP 4 compatibility of the shelf's MCP packages: untested.

## Sources

- MCP spec 2025-11-25, Tools: modelcontextprotocol.io/specification/2025-11-25/server/tools (read 2026-10-11)
- MCP spec 2025-11-25, Transports: modelcontextprotocol.io/specification/2025-11-25/basic/transports (read 2026-10-11)
- MCP spec 2026-07-28, Key changes: modelcontextprotocol.io/specification/2026-07-28/changelog (read 2026-10-11)
- FastMCP docs: gofastmcp.com/servers/tools, gofastmcp.com/servers/testing, gofastmcp.com/getting-started/upgrading/from-fastmcp-3 (read via fetch summary 2026-10-11; fetch summaries are secondary, the 3.4.4 / 4.1.0 installs back the behavior claims)
- FastMCP changelog / 3.0 coverage: gofastmcp.com/changelog and jlowin.dev/blog/fastmcp-3 (search snippets only, **untested**; the "sync tools run in a thread pool" claim in mcp.md rests on these)
- Anthropic, "Writing tools for agents", 2025-09-11: anthropic.com/engineering/writing-tools-for-agents
- MCP Inspector repo: github.com/modelcontextprotocol/inspector (read; commands not run)
- PyPI JSON for `fastmcp`, `mcp`, `fastmcp 4.1.0`, `mcp 2.3.0` (tested 2026-10-11)
- a2kay at ~/Workspaces/a2kay (read-only): pyproject.toml, uv.lock, tests/contracts/, tests/test_fastmcp_server.py, tests/test_serve_stdio_e2e.py, src/a2kay/routers/_base.py
