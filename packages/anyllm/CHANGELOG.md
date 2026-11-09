# anyllm — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see `ledger/0032-anyllm-v2-delivered.toml` for why). Read this before source/README when
reconciling a pin (agent-loop.md WORKFLOW: RECEIVE).

## 0.8.1

- claude-code-cli: an ambient `CLAUDE_CODE_SIMPLE` no longer reaches the child (it hid the subscription login); `ANTHROPIC_AUTH_TOKEN` or `CLAUDE_CODE_USE_BEDROCK/VERTEX/FOUNDRY` set in the environment ⇒ `ValueError` from the harness at launch. `anyllm[agent]` needs any-agent>=0.1.4

## 0.8.0

- BREAKING: claude-code-cli and codex-cli need anyllm[agent]; consumers on the default backend (a2kay) must add the extra when they bump
- Claude subprocess implementation ⇒ any-agent ClaudeHarness; add CodexCliAdapter / ProviderName.CODEX_CLI after Claude CLI in DEFAULT_ORDER; both CLI failures are non-retryable.
- Remove build_argv / child_env exports; billing safeguards are asserted on LaunchSpec.
- Pure completion by default on claude-code-cli and codex-cli: only the caller's system and user text; no host hooks, CLAUDE.md/AGENTS.md, memory, skills, plugins, MCP, tools or default coding prompt; one turn; empty temp cwd. System text REPLACES the default prompt (was appended on 0.7.0). Needs any-agent>=0.1.3 (`LaunchInputs.sealed`); subscription auth kept, ANTHROPIC_API_KEY scrubbed, never `--bare`
- CLI model ⇒ requested model (summary does not supply resolved model); Codex cost remains unknown (0.0).

## 0.4.0

- `ClaudeCodeSdkAdapter.available()`: true when `claude_agent_sdk` is importable  ⇒  true only when a `claude` CLI is locatable AND a session credential exists (`CLAUDE_CODE_OAUTH_TOKEN` / `~/.claude/.credentials.json` / macOS Keychain item)
- `ClaudeCodeSdkAdapter.complete()` precondition failure: always `"claude-agent-sdk is not installed"`  ⇒  distinguishes no-CLI from no-session, with a matching `hint`

Migration: an environment that installs the `claude-code-sdk` extra without logging in
now reports this backend unavailable instead of available-but-empty. Callers that rank
backends by `available()` will fall through to the next one, which is the intended fix.
A caller that *pinned* claude-code and relied on the old permissiveness will now see a
loud `AnyLLMError` at `complete()` naming the missing precondition, instead of silent
empty completions.

## 0.3.0

- `adapter.name`: plain `str`  ⇒  `ProviderName` enum (`str`-valued, so `==` against the
  old literals still holds)

## 0.2.0

- `LLMAdapter`  ⇒  `LLMProvider`
- `complete(prompt: str) -> str` (sync)  ⇒  `complete(*, user, system=(), model=None, max_tokens=1024, temperature=0.0, thinking_disabled=True, parts=None) -> Completion` (async)
- return: bare `str`  ⇒  `Completion` (text, model, prompt_tokens, completion_tokens, cost_usd, latency_ms, raw)
- failure: raises `AnyLLMError`  ⇒  unchanged (still fail-loud, `retryable`/`hint` preserved)
- backends: `claude-code-cli`, `anthropic-api`  ⇒  + `claude-code-sdk`, `openai-compatible`
- `anthropic-api` dep: `httpx`  ⇒  `anyllm[anthropic]` (official SDK)
- new: `PromptParts` (prompt-cache breakpoint hints), `available() -> bool` (per-adapter precondition probe)
