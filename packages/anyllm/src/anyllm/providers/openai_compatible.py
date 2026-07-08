"""openai-compatible backend — any ``chat/completions`` endpoint.

Speaks the contract against any OpenAI-compatible backend (OpenAI, Gemini's
compat endpoint, Ollama/LiteLLM, an operator gateway) via the ``openai`` SDK
(``anyllm[openai]`` extra) pointed at a ``base_url``. No JSON-mode / tool-use /
streaming — text in, text out. Pricing for arbitrary endpoints is unknown, so
``cost_usd`` is always ``0.0`` (the documented "could not price" sentinel).
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

from anyllm.base import Completion
from anyllm.errors import AnyLLMError
from anyllm.providers._prompt import flat_system, flat_user

if TYPE_CHECKING:
    from anyllm.base import PromptParts


class OpenAICompatibleAdapter:
    """Backend using the ``openai`` SDK against a configured ``base_url``."""

    name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str = "",
        api_key_env: str = "OPENAI_API_KEY",
        default_model: str = "",
        max_retries: int = 2,
    ) -> None:
        self._base_url = base_url
        self._api_key_env = api_key_env
        self._max_retries = max_retries
        self.default_model = default_model

    def available(self) -> bool:
        """Report whether an API key is resolvable from the configured env var."""
        return bool(os.environ.get(self._api_key_env, "").strip())

    def _client(self) -> Any:
        key = os.environ.get(self._api_key_env, "").strip()
        if not key:
            msg = f"no OpenAI-compatible API key (env {self._api_key_env})"
            raise AnyLLMError(msg, retryable=False, hint="set the key or configure another provider")
        from openai import AsyncOpenAI  # noqa: PLC0415 — lazy: the openai SDK is the optional [openai] extra

        endpoint = (self._base_url or "").strip()
        if endpoint:
            return AsyncOpenAI(api_key=key, base_url=endpoint, max_retries=self._max_retries)
        return AsyncOpenAI(api_key=key, max_retries=self._max_retries)

    async def complete(
        self,
        *,
        user: str,
        system: tuple[str, ...] | str = (),
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        thinking_disabled: bool = True,  # noqa: ARG002 - no thinking concept on OpenAI-compatible endpoints
        parts: PromptParts | None = None,
    ) -> Completion:
        """Send one chat completion and return a :class:`Completion`."""
        from openai import APIError  # noqa: PLC0415 — lazy: the openai SDK is the optional [openai] extra

        client = self._client()
        model_id = model or self.default_model
        messages: list[dict[str, str]] = []
        system_str = flat_system(parts, system)
        if system_str:
            messages.append({"role": "system", "content": system_str})
        messages.append({"role": "user", "content": flat_user(parts, user)})
        kwargs: dict[str, Any] = {"model": model_id, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}

        t0 = time.perf_counter()
        try:
            response = await client.chat.completions.create(**kwargs)
        except APIError as exc:
            status = getattr(exc, "status_code", None)
            retryable = status is None or status >= 500 or status == 429
            msg = f"OpenAI-compatible API error: {exc}"
            raise AnyLLMError(msg, retryable=retryable) from exc
        latency_ms = int((time.perf_counter() - t0) * 1000)

        text = response.choices[0].message.content or "" if response.choices else ""
        usage = response.usage
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage is not None else 0
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage is not None else 0
        return Completion(
            text=text,
            model=getattr(response, "model", model_id) or model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=0.0,  # unknown pricing for arbitrary endpoints — never guessed
            latency_ms=latency_ms,
        )


__all__ = ["OpenAICompatibleAdapter"]
