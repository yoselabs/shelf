"""Generic provider factory — map a provider name + config dict to a backend.

This is the mechanism (name → backend + availability check). *Where* the config
comes from (a registry file, env, a settings object) is the host app's policy and
stays in the host — a2kay reads its ``registry.yml`` and passes the ``llm`` section
here; a2web's manifest layer builds these directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from anyllm.errors import AnyLLMError
from anyllm.providers import (
    AnthropicApiAdapter,
    ClaudeCodeCliAdapter,
    ClaudeCodeSdkAdapter,
    OpenAICompatibleAdapter,
)

if TYPE_CHECKING:
    from anyllm.base import LLMProvider

DEFAULT_PROVIDER = "claude-code-cli"

_KNOWN = ("claude-code-cli", "claude-code-sdk", "anthropic-api", "openai-compatible")


def build_adapter(provider: str, config: dict | None = None) -> LLMProvider:
    """Return the configured backend, or raise :class:`AnyLLMError` if it is unusable.

    ``config`` holds the provider's options (e.g.
    ``{"anthropic_api": {"api_key_env": ...}}`` or
    ``{"openai_compatible": {"base_url": ..., "default_model": ...}}``). Raises if
    the name is unknown, or if the built backend is not available on this machine.
    """
    cfg = config or {}
    if provider == "claude-code-cli":
        adapter: LLMProvider = ClaudeCodeCliAdapter()
    elif provider == "claude-code-sdk":
        adapter = ClaudeCodeSdkAdapter()
    elif provider == "anthropic-api":
        raw = cfg.get("anthropic_api")
        api_cfg: dict = raw if isinstance(raw, dict) else {}
        adapter = AnthropicApiAdapter(api_key_env=str(api_cfg.get("api_key_env", "ANTHROPIC_API_KEY")))
    elif provider == "openai-compatible":
        raw = cfg.get("openai_compatible")
        oai_cfg: dict = raw if isinstance(raw, dict) else {}
        adapter = OpenAICompatibleAdapter(
            base_url=str(oai_cfg.get("base_url", "")),
            api_key_env=str(oai_cfg.get("api_key_env", "OPENAI_API_KEY")),
            default_model=str(oai_cfg.get("default_model", "")),
        )
    else:
        msg = f"unknown LLM provider: {provider!r}"
        raise AnyLLMError(msg, hint=f"use one of: {', '.join(_KNOWN)}")

    if not adapter.available():
        msg = f"LLM provider {provider!r} is configured but not usable on this machine"
        raise AnyLLMError(msg, hint="install the CLI/SDK or set the API key")
    return adapter


__all__ = ["DEFAULT_PROVIDER", "build_adapter"]
