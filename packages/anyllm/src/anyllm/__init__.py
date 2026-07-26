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
v0.5.0 adds :mod:`anyllm.cost` (a :class:`CostPolicy` + :func:`with_cost_guard`
that refuse expensive/metered spend before the call) — purely additive.
v0.6.0 adds :func:`resolve_provider` + :data:`DEFAULT_ORDER` (ordered
auto-selection with runtime fallback: walk a priority order, keep the usable
backends, fold them into one provider that advances to the next on a *retryable*
failure — a ``CostViolation`` propagates instead, never spending to recover) —
also purely additive.
"""

from __future__ import annotations

from anyllm.accounting import anthropic_cost_usd, extract_token_counts
from anyllm.base import Completion, LLMProvider, PromptParts, ProviderName
from anyllm.cost import (
    DEFAULT_COST_POLICY,
    CostPolicy,
    CostViolation,
    assert_within_budget,
    with_cost_guard,
)
from anyllm.errors import AnyLLMError
from anyllm.providers import (
    AnthropicApiAdapter,
    ClaudeCodeCliAdapter,
    ClaudeCodeSdkAdapter,
    OpenAICompatibleAdapter,
    build_argv,
    child_env,
)
from anyllm.select import DEFAULT_ORDER, DEFAULT_PROVIDER, build_adapter, resolve_provider

__all__ = [
    "DEFAULT_COST_POLICY",
    "DEFAULT_ORDER",
    "DEFAULT_PROVIDER",
    "AnthropicApiAdapter",
    "AnyLLMError",
    "ClaudeCodeCliAdapter",
    "ClaudeCodeSdkAdapter",
    "Completion",
    "CostPolicy",
    "CostViolation",
    "LLMProvider",
    "OpenAICompatibleAdapter",
    "PromptParts",
    "ProviderName",
    "anthropic_cost_usd",
    "assert_within_budget",
    "build_adapter",
    "build_argv",
    "child_env",
    "extract_token_counts",
    "resolve_provider",
    "with_cost_guard",
]
