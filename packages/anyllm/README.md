# anyllm

Stop caring which LLM provider is underneath. A minimal, neutral completion
interface with two shipped backends and a generic factory. No dependency on any
host framework — adapters raise `AnyLLMError`; you translate it into your own
error type at the seam.

```python
from anyllm import build_adapter

adapter = build_adapter("claude-code-cli")        # or "anthropic-api"
text = adapter.complete("Summarize this.", model=None)
```

## Backends

- **`claude-code-cli`** — subscription-billed `claude -p --output-format json`.
  Scrubs `ANTHROPIC_API_KEY` from the child env and never passes `--bare`, so it
  cannot silently fall back to (and bill) the per-token API. Fails loud on a
  non-zero exit; never retries against the API.
- **`anthropic-api`** — the per-token Messages API over `httpx`, with bounded
  exponential-backoff retry on network errors + 429/5xx (honoring `Retry-After`).

## The interface

```python
class LLMAdapter(Protocol):
    name: str
    def complete(self, prompt: str, *, model: str | None = None) -> str: ...
    def available(self) -> bool: ...   # cheap probe — usable on this machine now?
```

`build_adapter(provider, config)` maps a provider name + options to an adapter and
raises `AnyLLMError` if the provider is unknown or unavailable. *Where* the config
comes from (a file, env, a settings object) is the host's business.
