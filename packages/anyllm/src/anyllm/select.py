"""Generic provider factory — map a provider name + config dict to an adapter.

This is the mechanism (name → adapter + availability check). Reading *where* the
config comes from (a registry file, env, a settings object) is the host app's
policy and stays in the host — a2kay reads its ``registry.yml`` and passes the
``llm`` section here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from anyllm.anthropic_api import AnthropicApiAdapter
from anyllm.claude_code_cli import ClaudeCodeCliAdapter
from anyllm.errors import AnyLLMError

if TYPE_CHECKING:
    from anyllm.base import LLMAdapter

DEFAULT_PROVIDER = "claude-code-cli"


def build_adapter(provider: str, config: dict | None = None) -> LLMAdapter:
    """Return the configured adapter, or raise :class:`AnyLLMError` if it is unusable.

    ``config`` is the provider's options (e.g. ``{"anthropic_api": {"api_key_env": ...}}``).
    Raises if the provider name is unknown, or if the built adapter is not available on
    this machine (missing CLI / missing key).
    """
    cfg = config or {}
    if provider == "anthropic-api":
        raw = cfg.get("anthropic_api")
        api_cfg: dict = raw if isinstance(raw, dict) else {}
        adapter: LLMAdapter = AnthropicApiAdapter(api_key_env=str(api_cfg.get("api_key_env", "ANTHROPIC_API_KEY")))
    elif provider == "claude-code-cli":
        adapter = ClaudeCodeCliAdapter()
    else:
        msg = f"unknown LLM provider: {provider!r}"
        raise AnyLLMError(msg, hint="use claude-code-cli or anthropic-api")

    if not adapter.available():
        msg = f"LLM provider {provider!r} is configured but not usable on this machine"
        raise AnyLLMError(
            msg,
            hint="install the CLI or set the API key",
        )
    return adapter


__all__ = ["DEFAULT_PROVIDER", "build_adapter"]
