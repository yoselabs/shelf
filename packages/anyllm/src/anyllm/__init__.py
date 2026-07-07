"""anyllm — stop caring which LLM provider is underneath.

A minimal, neutral completion interface (:class:`LLMAdapter`) with two shipped
backends — ``claude-code-cli`` (subscription-billed ``claude -p``, scrubbing
``ANTHROPIC_API_KEY`` so it never silently bills the API) and ``anthropic-api``
(per-token Messages API with bounded retry) — plus a generic :func:`build_adapter`
factory. Adapters fail loud with :class:`AnyLLMError`; the host translates it into
its own error taxonomy at the seam.

Design law (hide compute, surface state): the ``complete`` boundary is clean and
swappable; provider *availability* is surfaced (``available()``) so the host can
fail loud rather than silently degrade.
"""

from __future__ import annotations

from anyllm.anthropic_api import AnthropicApiAdapter
from anyllm.base import LLMAdapter
from anyllm.claude_code_cli import ClaudeCodeCliAdapter, build_argv, child_env
from anyllm.errors import AnyLLMError
from anyllm.select import DEFAULT_PROVIDER, build_adapter

__all__ = [
    "DEFAULT_PROVIDER",
    "AnthropicApiAdapter",
    "AnyLLMError",
    "ClaudeCodeCliAdapter",
    "LLMAdapter",
    "build_adapter",
    "build_argv",
    "child_env",
]
