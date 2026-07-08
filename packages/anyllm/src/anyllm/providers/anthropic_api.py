"""anthropic-api backend — per-token Messages API via the official async SDK.

v0.2.0: was a raw-httpx sync adapter; now the ``anthropic`` AsyncAnthropic SDK
(behind the ``anyllm[anthropic]`` extra) so it can place prompt-cache breakpoints
and read cache-tier usage. The SDK's own ``max_retries`` handles transient retry;
on exhaustion its ``APIError`` is translated to a fail-loud :class:`AnyLLMError`.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

from anyllm.accounting import anthropic_cost_usd, extract_token_counts
from anyllm.base import Completion
from anyllm.errors import AnyLLMError
from anyllm.providers._prompt import resolve_system

if TYPE_CHECKING:
    from anyllm.base import PromptParts

_DEFAULT_MODEL = "claude-sonnet-4-6"
_RETRYABLE_STATUSES = frozenset({408, 409, 429, 500, 502, 503, 504, 529})


class AnthropicApiAdapter:
    """Completion backend calling the Anthropic Messages API (async SDK)."""

    name = "anthropic-api"

    def __init__(self, *, api_key_env: str = "ANTHROPIC_API_KEY", api_key: str | None = None, max_retries: int = 2) -> None:
        self._api_key_env = api_key_env
        self._api_key = api_key
        self._max_retries = max_retries

    def _key(self) -> str | None:
        return self._api_key or os.environ.get(self._api_key_env)

    def available(self) -> bool:
        """Report whether an API key is resolvable (literal or from the env var)."""
        return bool(self._key())

    def _client(self) -> Any:
        key = self._key()
        if not key:
            msg = f"no Anthropic API key (env {self._api_key_env})"
            raise AnyLLMError(msg, retryable=False, hint="set the key or configure another provider")
        from anthropic import AsyncAnthropic  # noqa: PLC0415 — lazy: the anthropic SDK is the optional [anthropic] extra

        return AsyncAnthropic(api_key=key, max_retries=self._max_retries)

    async def complete(
        self,
        *,
        user: str,
        system: tuple[str, ...] | str = (),
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        thinking_disabled: bool = True,  # noqa: ARG002 - contract param; SDK default already disables thinking
        parts: PromptParts | None = None,
    ) -> Completion:
        """Send one user message (+ optional system) and return a :class:`Completion`."""
        from anthropic import APIError  # noqa: PLC0415 — lazy: the anthropic SDK is the optional [anthropic] extra

        client = self._client()
        model_id = model or _DEFAULT_MODEL
        kwargs = _build_kwargs(model_id, user=user, system=system, max_tokens=max_tokens, temperature=temperature, parts=parts)

        t0 = time.perf_counter()
        try:
            response = await client.messages.create(**kwargs)
        except APIError as exc:
            status = getattr(exc, "status_code", None)
            retryable = status in _RETRYABLE_STATUSES if status is not None else True
            msg = f"Anthropic API error: {exc}"
            raise AnyLLMError(msg, retryable=retryable) from exc
        latency_ms = int((time.perf_counter() - t0) * 1000)

        text = "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", None) == "text")
        prompt_tokens, completion_tokens, cache_creation, cache_read = extract_token_counts(response.usage)
        cost = anthropic_cost_usd(
            response.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_creation=cache_creation,
            cache_read=cache_read,
        )
        return Completion(
            text=text,
            model=response.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )


def _build_kwargs(
    model: str,
    *,
    user: str,
    system: tuple[str, ...] | str,
    max_tokens: int,
    temperature: float,
    parts: PromptParts | None,
) -> dict[str, Any]:
    """Assemble the ``messages.create`` kwargs, placing cache breakpoints when ``parts`` asks."""
    kwargs: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "temperature": temperature}
    if parts is not None and parts.cache_prefix != "":
        kwargs["messages"] = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": parts.cache_prefix, "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": parts.tail},
                ],
            }
        ]
        if parts.system:
            kwargs["system"] = [{"type": "text", "text": parts.system, "cache_control": {"type": "ephemeral"}}]
    else:
        kwargs["messages"] = [{"role": "user", "content": user}]
        system_str = resolve_system(system)
        if system_str:
            kwargs["system"] = system_str
    return kwargs


__all__ = ["AnthropicApiAdapter"]
