"""Refuse expensive model spend before the completion call is issued.

A :class:`CostPolicy` is an allowlist over ``(provider, model-glob)`` pairs.
:func:`with_cost_guard` wraps any :class:`~anyllm.base.LLMProvider` so every
``complete()`` asserts the resolved ``(provider.name, model)`` pair against the
policy **before** the network call — a denied pair raises :class:`CostViolation`
and no spend happens. Because the guarded provider is the only handle a caller
holds, no un-guarded completion path exists: it is impossible to bill a
disallowed model by accident, rather than merely discouraged.

Keyed on :class:`~anyllm.base.ProviderName` (the canonical backend id), not a
host's own provider alias: the cost distinction (flat subscription vs. metered
per-token) is a property of the *backend*, so the enum is exactly the right key.
The default policy encodes "expensive models only via subscription, never
metered": the two subscription backends (``claude-code-cli`` / ``-sdk``) allow
any model, the metered ``anthropic-api`` allows cheap (Haiku-class) models only,
``openai-compatible`` allows a conservative cheap allowlist, and any pair not in
the table is DENIED — a new model is opted in deliberately, never by accident.

Host-agnostic (no framework imports): a host reads its own config to choose a
policy and translates :class:`CostViolation` at its own seam if it wants a
domain error.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Any

from anyllm.base import ProviderName

if TYPE_CHECKING:
    from anyllm.base import Completion, LLMProvider, PromptParts


class CostViolation(RuntimeError):  # noqa: N818 — a budget refusal, not an operational error; the deliberate non-"Error" name marks it as a policy verdict callers assert on.
    """Raised when a ``(provider, model)`` pair is not permitted by the policy."""


@dataclass(frozen=True, slots=True)
class CostPolicy:
    """Per-provider allow-globs over lowercased model ids.

    Stored as a tuple of ``(provider, patterns)`` pairs (not a dict) so the
    policy stays a frozen, hashable, immutable boundary value. A provider absent
    from the table is DENIED — the safe default (fail loud, opt in deliberately).
    """

    allow: tuple[tuple[ProviderName, tuple[str, ...]], ...]

    def permits(self, provider: ProviderName | str, model: str) -> bool:
        """Return whether ``model`` is allowed for ``provider`` under this policy.

        ``provider`` may be a :class:`ProviderName` or its bare string value
        (``ProviderName`` is a ``StrEnum``, so both compare equal). An unlisted
        provider returns ``False``.
        """
        m = (model or "").lower()
        return any(pid == provider and any(fnmatch(m, p) for p in patterns) for pid, patterns in self.allow)


# "Expensive models only via subscription, never metered." The two claude-code
# backends are flat-cost (subscription) so any model is fine — the Sonnet judge
# is free there. Metered anthropic-api is cheap-models-only (Haiku-class).
# openai-compatible is a last-resort gateway: a conservative cheap allowlist,
# everything else denied, so an unrecognised OpenAI model is refused (fail loud)
# rather than billed.
DEFAULT_COST_POLICY = CostPolicy(
    allow=(
        (ProviderName.CLAUDE_CODE_CLI, ("*",)),
        (ProviderName.CLAUDE_CODE_SDK, ("*",)),
        (ProviderName.ANTHROPIC_API, ("*haiku*",)),
        (ProviderName.OPENAI_COMPATIBLE, ("*mini*", "*nano*", "*flash*", "*small*", "*7b*", "*8b*", "*haiku*")),
    )
)


def assert_within_budget(
    provider: ProviderName | str,
    model: str,
    policy: CostPolicy = DEFAULT_COST_POLICY,
) -> None:
    """Raise :class:`CostViolation` unless ``(provider, model)`` is permitted.

    Args:
        provider: The backend id (a :class:`ProviderName` or its string value).
        model: The concrete model id the call would run against.
        policy: The allowlist to assert against (defaults to the cheap policy).

    Raises:
        CostViolation: When the pair is not in the policy allowlist.
    """
    if not policy.permits(provider, model):
        msg = (
            f"provider={str(provider)!r} model={model!r} is not permitted by the cost "
            "policy — refusing to bill an expensive or metered model. Use a flat-cost "
            "subscription backend, or add the pair to the CostPolicy allowlist to opt in "
            "deliberately."
        )
        raise CostViolation(msg)


class _GuardedProvider:
    """An :class:`~anyllm.base.LLMProvider` wrapper that cost-asserts, then delegates.

    Structural (duck-typed) provider — exposes ``name`` / ``complete`` /
    ``available`` and forwards any other attribute (e.g. ``default_model``) to
    the wrapped provider.
    """

    def __init__(self, inner: LLMProvider, policy: CostPolicy) -> None:
        self._inner = inner
        self._policy = policy
        self.name: ProviderName = inner.name

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
        """Assert the resolved ``(name, model)`` pair, then delegate to the inner provider."""
        # Resolve the model the call would actually run against, then assert
        # BEFORE issuing the network call — no spend happens on a denied pair.
        effective = model or getattr(self._inner, "default_model", "") or ""
        assert_within_budget(self.name, effective, self._policy)
        return await self._inner.complete(
            user=user,
            system=system,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            thinking_disabled=thinking_disabled,
            parts=parts,
        )

    def available(self) -> bool:
        """Delegate the usability probe to the wrapped provider."""
        return self._inner.available()

    def __getattr__(self, item: str) -> Any:
        # Forward unknown attributes (default_model, etc.) to the inner
        # provider. Guarded against recursion before _inner is set.
        inner = self.__dict__.get("_inner")
        if inner is None:
            raise AttributeError(item)
        return getattr(inner, item)


def with_cost_guard(provider: LLMProvider, policy: CostPolicy = DEFAULT_COST_POLICY) -> LLMProvider:
    """Wrap ``provider`` so every ``complete()`` is cost-asserted first.

    The policy keys on ``provider.name`` (a :class:`ProviderName`) — the caller
    passes no separate id. Returns a provider satisfying the same
    :class:`~anyllm.base.LLMProvider` contract, so it is a drop-in replacement.

    Args:
        provider: The backend to guard.
        policy: The allowlist to enforce (defaults to the cheap policy).

    Returns:
        A guarded provider that raises :class:`CostViolation` on a denied pair
        before issuing any network call.
    """
    return _GuardedProvider(provider, policy)  # type: ignore[return-value]


__all__ = [
    "DEFAULT_COST_POLICY",
    "CostPolicy",
    "CostViolation",
    "assert_within_budget",
    "with_cost_guard",
]
