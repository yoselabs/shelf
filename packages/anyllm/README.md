# anyllm

Stop caring which LLM provider is underneath. One async, structured completion
contract returning a rich `Completion` (text + token/cost/latency accounting),
with four shipped backends behind one interface. No dependency on any host
framework — backends **fail loud** with `AnyLLMError`; you translate it into your
own error type, or catch it to degrade, at your own seam.

```python
from anyllm import build_adapter

adapter = build_adapter("claude-code-cli")            # or -sdk / anthropic-api / openai-compatible
result = await adapter.complete(user="Summarize this.")
print(result.text, result.cost_usd, result.prompt_tokens)
```

## Backends

Base install is featherweight (the CLI backend is stdlib-only). Each SDK-backed
backend is an opt-in extra so you pull only the provider libraries you use.

- **`claude-code-cli`** *(no extra)* — subscription-billed `claude -p --output-format json`.
  Scrubs `ANTHROPIC_API_KEY` from the child env and never passes `--bare`, so it
  cannot silently fall back to (and bill) the per-token API. Fails loud on a
  non-zero exit; never retries against the API.
- **`claude-code-sdk`** *(`anyllm[claude-code-sdk]`)* — the OAuth OS session via
  `claude-agent-sdk`. Single-turn pure completion; host CLAUDE.md / skills / MCP
  servers / subagents are all blocked so no personal context leaks in.
- **`anthropic-api`** *(`anyllm[anthropic]`)* — the per-token Messages API via the
  official async SDK, with prompt-cache breakpoints and cache-tier cost accounting.
  The SDK's own `max_retries` handles transient retry; exhaustion fails loud.
- **`openai-compatible`** *(`anyllm[openai]`)* — any `chat/completions` endpoint
  (OpenAI, Gemini-compat, Ollama/LiteLLM, a gateway). `cost_usd` is always `0.0`
  (unknown pricing is never guessed).

## The contract

```python
@dataclass(slots=True)
class Completion:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    raw: dict | None = None

class LLMProvider(Protocol):
    name: str
    async def complete(
        self, *, user: str, system: tuple[str, ...] | str = (), model: str | None = None,
        max_tokens: int = 1024, temperature: float = 0.0, thinking_disabled: bool = True,
        parts: PromptParts | None = None,
    ) -> Completion: ...
    def available(self) -> bool: ...   # cheap probe — usable on this machine now?
```

`build_adapter(provider, config)` maps a provider name + options to a backend and
raises `AnyLLMError` if the provider is unknown or unavailable. *Where* the config
comes from (a file, env, a settings object) is the host's business.

## Migrating v0.1 → v0.2 (breaking)

v0.2.0 evolved the contract to a superset (resolution 0007, the *monotonicity
test*): it only expands exposure and removes nothing. `anyllm-v0.1.0` stays
tagged — upgrade when you're ready.

| v0.1 | v0.2 |
|---|---|
| `LLMAdapter` | `LLMProvider` |
| `text = adapter.complete("prompt")` (sync, `-> str`) | `result = await adapter.complete(user="prompt")` (async, `-> Completion`); read `result.text` |
| provider failure raises `AnyLLMError` | unchanged — still fail-loud (`retryable`/`hint` preserved) |
| `anthropic-api` pulled `httpx` | now `anyllm[anthropic]` (official SDK); `claude-code-cli` stays dependency-free |

New in v0.2: token/cost/latency on every result, prompt-cache breakpoints
(`PromptParts`), and two more backends (`claude-code-sdk`, `openai-compatible`).
