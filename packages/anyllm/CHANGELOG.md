# anyllm — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see `ledger/0032-anyllm-v2-delivered.toml` for why). Read this before source/README when
reconciling a pin (agent-loop.md WORKFLOW: RECEIVE).

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
