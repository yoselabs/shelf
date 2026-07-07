"""anthropic-api adapter — per-token Messages API via httpx (ADR 0019).

Secondary provider. Uses the existing ``httpx`` dep; the key comes from
machine-local config (an env-var name or literal), never the vault.
"""

from __future__ import annotations

import os
import time

import httpx

from anyllm.errors import AnyLLMError

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_DEFAULT_MODEL = "claude-sonnet-4-6"

# Retry policy for transient failures (network errors + 429/5xx). Bounded
# exponential backoff; `Retry-After` wins when the server sends it. `_sleep` is
# module-level so tests can substitute it.
_MAX_ATTEMPTS = 3
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504, 529})
_BACKOFF_BASE = 0.5
_sleep = time.sleep


def _backoff(attempt: int, resp: httpx.Response | None) -> float:
    if resp is not None:
        retry_after = resp.headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
    return _BACKOFF_BASE * (2**attempt)


class AnthropicApiAdapter:
    """LLM adapter calling the Anthropic Messages API over httpx with bounded retries."""

    name = "anthropic-api"

    def __init__(self, *, api_key_env: str = "ANTHROPIC_API_KEY", api_key: str | None = None, max_tokens: int = 4096) -> None:
        self._api_key_env = api_key_env
        self._api_key = api_key
        self._max_tokens = max_tokens

    def _key(self) -> str | None:
        return self._api_key or os.environ.get(self._api_key_env)

    def available(self) -> bool:
        """Report whether an API key is resolvable (literal or from the env var)."""
        return bool(self._key())

    def complete(self, prompt: str, *, model: str | None = None) -> str:
        """Send the prompt to the Messages API and return the concatenated text response."""
        key = self._key()
        if not key:
            msg = f"no Anthropic API key (env {self._api_key_env})"
            raise AnyLLMError(
                msg,
                retryable=False,
                hint="set the key or configure another provider",
            )
        headers = {"x-api-key": key, "anthropic-version": _API_VERSION, "content-type": "application/json"}
        body = {
            "model": model or _DEFAULT_MODEL,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        for attempt in range(_MAX_ATTEMPTS):
            last = attempt + 1 == _MAX_ATTEMPTS
            try:
                resp = httpx.post(_API_URL, headers=headers, json=body, timeout=120.0)
            except httpx.HTTPError as exc:
                if last:
                    msg = f"Anthropic API request failed: {exc}"
                    raise AnyLLMError(msg, retryable=True) from exc
                _sleep(_backoff(attempt, None))
                continue
            if resp.status_code == 200:
                return _extract_text(resp.json())
            retryable = resp.status_code in _RETRYABLE_STATUSES
            if retryable and not last:
                _sleep(_backoff(attempt, resp))
                continue
            msg = f"Anthropic API {resp.status_code}: {resp.text[:300]}"
            raise AnyLLMError(msg, retryable=retryable)
        # unreachable: the loop either returns or raises on the final attempt
        msg = "Anthropic API: retry budget exhausted"
        raise AnyLLMError(msg, retryable=True)


def _extract_text(payload: dict) -> str:
    blocks = payload.get("content") if isinstance(payload, dict) else None
    if isinstance(blocks, list):
        text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
        if text:
            return text
    raise AnyLLMError(f"Anthropic API response lacked text content: {payload!r}"[:300], retryable=False)


__all__ = ["AnthropicApiAdapter"]
