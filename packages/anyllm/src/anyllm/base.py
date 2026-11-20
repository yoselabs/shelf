"""The LLM provider contract — one async call, one rich result.

v0.2.0 (ADR 0007, the monotonicity test) evolved this from the v0.1
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
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast, runtime_checkable

from anyllm.errors import AnyLLMError

if TYPE_CHECKING:
    from collections.abc import Mapping

Effort = Literal["low", "medium", "high"]


class ProviderName(StrEnum):
    """One source of truth for backend names — every adapter's ``.name`` is one of these.

    Added v0.3.0 after two independent vocabularies for the same four backends drifted
    apart (anyllm's own bare ``str`` values here vs. a2web's separately-invented plugin
    names, e.g. ``"claude-code-sdk"`` vs. ``"claude-code"``). A ``StrEnum`` member compares
    equal to its string value, so this is additive — no caller comparing against the
    literal string breaks.
    """

    CLAUDE_CODE_CLI = "claude-code-cli"
    CODEX_CLI = "codex-cli"
    CLAUDE_CODE_SDK = "claude-code-sdk"
    ANTHROPIC_API = "anthropic-api"
    OPENAI_COMPATIBLE = "openai-compatible"


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

    @property
    def name(self) -> ProviderName:
        """The backend identity exposed by this provider."""
        ...

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


@runtime_checkable
class StructuredProvider(LLMProvider, Protocol):
    """A backend that enforces a JSON Schema on the answer and takes a reasoning effort (today: ``codex-cli``).

    Kept off :class:`LLMProvider`: a backend that cannot meet these must not accept them. ``supports_structured`` is the marker
    :func:`require_structured` checks (``isinstance`` against a Protocol checks method names only, so it cannot tell them apart).
    """

    supports_structured: bool

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
        response_schema: Mapping[str, Any] | None = None,
        effort: Effort | None = None,
    ) -> Completion:
        """As :meth:`LLMProvider.complete`; with ``response_schema`` ``Completion.text`` is schema-valid JSON text.

        ``effort=None`` keeps the backend's default (``low`` on codex-cli).
        """
        ...


def require_structured(provider: LLMProvider) -> StructuredProvider:
    """``provider`` as a :class:`StructuredProvider`, or :class:`AnyLLMError` (never a silent ignore of schema or effort)."""
    if getattr(provider, "supports_structured", False) is not True:
        msg = f"{provider.name} cannot enforce a response schema or an effort"
        raise AnyLLMError(msg, retryable=False, hint="use provider codex-cli, or drop response_schema / effort")
    return cast("StructuredProvider", provider)


__all__ = ["Completion", "Effort", "LLMProvider", "PromptParts", "ProviderName", "StructuredProvider", "require_structured"]
