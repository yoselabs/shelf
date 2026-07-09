# anyllm — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see `ledger/0032-anyllm-v2-delivered.toml` for why). Read this before source/README when
reconciling a pin (agent-loop.md WORKFLOW: RECEIVE).

## 0.2.0

- `LLMAdapter`  ⇒  `LLMProvider`
- `complete(prompt: str) -> str` (sync)  ⇒  `complete(*, user, system=(), model=None, max_tokens=1024, temperature=0.0, thinking_disabled=True, parts=None) -> Completion` (async)
- return: bare `str`  ⇒  `Completion` (text, model, prompt_tokens, completion_tokens, cost_usd, latency_ms, raw)
- failure: raises `AnyLLMError`  ⇒  unchanged (still fail-loud, `retryable`/`hint` preserved)
- backends: `claude-code-cli`, `anthropic-api`  ⇒  + `claude-code-sdk`, `openai-compatible`
- `anthropic-api` dep: `httpx`  ⇒  `anyllm[anthropic]` (official SDK)
- new: `PromptParts` (prompt-cache breakpoint hints), `available() -> bool` (per-adapter precondition probe)
