## 1. Package scaffold

- [x] 1.1 Create `packages/mcp-feedback/` (`pyproject.toml`, `README.md`,
      `src/mcp_feedback/__init__.py`, `tests/`) mirroring
      `packages/mcp-result-wire/` layout.
- [x] 1.2 Add `fastmcp` + `httpx` as this package's dependencies; add the
      workspace member entry. (Workspace members are `packages/*` glob —
      no root pyproject.toml edit needed.)
- [x] 1.3 Add `catalog/mcp-feedback.toml` (`kind = "any-*"`, `tier = "T2"`,
      `status = "candidate"`, `implementation = "ours"`) per D1.

## 2. Transport

- [x] 2.1 Implement the OTLP/HTTP-logs POST helper (async `httpx`, 5s
      timeout, `X-Api-Key` header, swallow `httpx.HTTPError`/`OSError` into
      a warning, never raise) per design D6.
- [x] 2.2 Result type: `FeedbackReportResult{sent: bool}` — attempt, not
      delivery confirmation.

## 3. Tool registration

- [x] 3.1 Implement `register_feedback_tool(mcp, *, endpoint, api_key,
      extra_instructions=None)` mounting `report_feedback(subject, note,
      wanted=None)` with the fixed base docstring + optional appended
      `extra_instructions` per D4.
- [x] 3.2 ~~Attach `ctx.session_id` to every outgoing report per D5~~ —
      **reversed in v0.2.0** (design D5 addendum): no `Context` parameter,
      no correlation ID at all. Reports are self-contained; the tool's
      description asks the agent to include what context it needs.
- [x] 3.3 Gate on `endpoint`/`api_key` both present; `sent=False` no-op
      otherwise.

## 4. Tests

- [x] 4.1 `test_mcp_feedback.py` — schema fixture: two independently
      configured registrations produce identical tool name/params/types
      (spec: "Two independent consumers mount an identical schema").
- [x] 4.2 `test_property_*.py` — `extra_instructions` appends without
      replacing the base docstring; omitted case leaves only the base text.
- [x] 4.3 `test_boundary_mcp_feedback.py` — delivery failure swallowed,
      `sent=True` still returned; not-configured case returns `sent=False`
      with zero network calls; confirms no `opentelemetry-sdk` import
      anywhere in the package.
- [x] 4.4 ~~Test that `session_id` is present on every outgoing payload~~ —
      replaced (v0.2.0) with `test_no_correlation_id_is_attached` (report
      contains exactly `subject`/`note`/`wanted`, nothing else) and
      `test_tool_function_callable_without_a_live_mcp_session` (the
      underlying function runs with no active FastMCP request/session —
      the actual reason for the reversal).

## 5. Verification

- [x] 5.1 `make check` passes (lint + ty + test) for the whole shelf repo.
- [x] 5.2 `openspec validate add-mcp-feedback-package --strict` passes.
- [x] 5.3 v0.2.0: re-tag `mcp-feedback-v0.2.0`, push, and re-run the
      consuming a2web change's CLI contract suite to confirm the original
      blocker (Context-requiring tool function breaks a2web's raw-signature
      CLI derivation) is actually resolved, not just theorized.

## 6. `request`/`response` fields (v0.3.0)

- [x] 6.1 Add `request: str | None = None` and `response: str | None =
      None` to `report_feedback`'s signature (after `note`, before
      `wanted`), free text, no taxonomy — per design D7.
- [x] 6.2 Update `_BASE_DESCRIPTION` to name the new fields and clarify
      only `subject`/`note` are required.
- [x] 6.3 Update tests: schema now has 5 properties; a report carrying
      all fields round-trips correctly; `request`/`response` omitted when
      not supplied.
- [x] 6.4 `make check` passes; re-tag `mcp-feedback-v0.3.0`, push.
