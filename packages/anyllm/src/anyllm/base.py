"""The LLM provider contract — one async call, one rich result.

v0.2.0 (resolution 0007, the monotonicity test) evolved this from the v0.1
``LLMAdapter`` (sync, ``complete(prompt) -> str``). The unified contract only
*expands* exposure and removes nothing a caller relied on:

- **Rich return** (:class:`Completion`) instead of a bare string — token counts,
  ``cost_usd``, ``latency_ms`` ride along; a caller that only wants the text reads
  ``.text``.
- **Fail-loud** everywhere — a provider failure raises :class:`~anyllm.errors.AnyLLMError`
  (with ``retryable`` / ``hint``); it never returns an empty string as a silent
  error. A consumer that wants to *degrade* on failure catches the error at its
  own seam.
- **Async + structured** ``complete(*, system, user, …)`` — the one call
  convention. A flat prompt is ``complete(user=prompt)``; ``system=()`` is the
  no-system-content shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class PromptParts:
    """A rendered prompt split for prompt-cache breakpoint placement.

    ``system`` and ``cache_prefix`` together form the byte-stable prefix a
    provider's caching layer keys on; ``tail`` carries the per-call variable
    portion. A non-cacheable prompt renders with ``cache_prefix=""`` — providers
    then concatenate ``cache_prefix + tail`` and behave as a flat prompt.

    Optional: it is a *hint*. Providers without a cache-marker API fall back to
    byte-equivalent concatenation; passing ``parts=None`` uses the flat path.
    """

    system: str
    cache_prefix: str
    tail: str


@dataclass(slots=True)
class Completion:
    """One completion result. Token counts and cost are best-effort.

    ``cost_usd == 0.0`` means the provider could not price the call (a cache-only
    turn, or a backend with no pricing table) — not "free". ``raw`` carries
    provider-specific debug data; never depend on its shape from outside.
    """

    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    raw: dict[str, Any] | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """A completion backend. Implementations fail loud, never silent."""

    name: str

    async def complete(
        self,
        *,
        user: str,
        system: tuple[str, ...] | str = (),
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        thinking_disabled: bool = True,
        parts: PromptParts | None = None,
    ) -> Completion:
        """Complete ``user`` (with optional ``system`` content) into a :class:`Completion`.

        ``system=()`` or ``system=""`` sends no system content. ``thinking_disabled``
        disables extended thinking on backends that support it. ``parts`` — when its
        ``cache_prefix`` is non-empty — asks the backend to place a prompt-cache
        breakpoint; backends without a marker API fall back to concatenation.

        Raises :class:`~anyllm.errors.AnyLLMError` on any provider failure
        (transient failures carry ``retryable=True``). Programmer errors propagate.
        """
        ...

    def available(self) -> bool:
        """Cheap probe: is this provider usable on this machine right now?"""
        ...


__all__ = ["Completion", "LLMProvider", "PromptParts"]
