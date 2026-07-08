"""anyllm — stop caring which LLM provider is underneath.

One async, structured completion contract (:class:`LLMProvider`) returning a rich
:class:`Completion` (text + token/cost/latency accounting), with four shipped
backends behind one interface:

- ``claude-code-cli`` — subscription-billed ``claude -p`` (stdlib subprocess, no
  extra; scrubs ``ANTHROPIC_API_KEY`` so it never silently bills the API),
- ``claude-code-sdk`` — the OAuth OS session via ``claude-agent-sdk``
  (``anyllm[claude-code-sdk]``),
- ``anthropic-api`` — per-token Messages API (``anyllm[anthropic]``),
- ``openai-compatible`` — any ``chat/completions`` endpoint (``anyllm[openai]``).

Backends **fail loud** with :class:`AnyLLMError`; the host translates it into its
own error taxonomy — or catches it to degrade — at its own seam. Design law (hide
compute, surface state): ``complete`` is clean and swappable; provider
*availability* is surfaced (``available()``) so a host fails loud rather than
silently degrading.

Evolved from v0.1's sync ``complete(prompt) -> str`` per resolution 0007 (the
monotonicity test); v0.1.0 stays tagged for consumers that have not upgraded.
"""

from __future__ import annotations

from anyllm.accounting import anthropic_cost_usd, extract_token_counts
from anyllm.base import Completion, LLMProvider, PromptParts
from anyllm.errors import AnyLLMError
from anyllm.providers import (
    AnthropicApiAdapter,
    ClaudeCodeCliAdapter,
    ClaudeCodeSdkAdapter,
    OpenAICompatibleAdapter,
    build_argv,
    child_env,
)
from anyllm.select import DEFAULT_PROVIDER, build_adapter

__all__ = [
    "DEFAULT_PROVIDER",
    "AnthropicApiAdapter",
    "AnyLLMError",
    "ClaudeCodeCliAdapter",
    "ClaudeCodeSdkAdapter",
    "Completion",
    "LLMProvider",
    "OpenAICompatibleAdapter",
    "PromptParts",
    "anthropic_cost_usd",
    "build_adapter",
    "build_argv",
    "child_env",
    "extract_token_counts",
]
