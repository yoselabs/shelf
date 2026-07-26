"""Generic provider selection — name → backend, and ordered auto-selection.

Two layers:

- :func:`build_adapter` — the *single-provider* mechanism (name → backend +
  availability check). *Where* the config comes from (a registry file, env, a
  settings object) is the host app's policy and stays in the host — a2kay reads
  its ``registry.yml`` and passes the ``llm`` section here; a2web's manifest layer
  builds these directly.
- :func:`resolve_provider` — the *multi-provider* mechanism: walk an ordered list
  of candidates, keep the ones this machine can build+run, and (by default) fold
  them into one provider that **falls back at runtime** — if the chosen backend
  raises a *retryable* :class:`~anyllm.errors.AnyLLMError` mid-call, the next
  candidate serves. The *order* (which backends, in what priority) is the host's
  policy and is passed in; only the *mechanism* lives here. ``auto`` is a
  selection outcome, never a :class:`~anyllm.base.ProviderName` — you resolve an
  order into a concrete provider, you do not name "auto" as a backend.

Cost safety is structural, not a special case: :class:`~anyllm.cost.CostViolation`
is a ``RuntimeError``, not an :class:`~anyllm.errors.AnyLLMError`, so it propagates
straight through the runtime fallback — a budget refusal never "spends more to
recover" onto a metered backend. Wrap each candidate with the cost guard via the
``wrap`` hook (applied per-candidate, before composition, so the guard sees the
real backend id — not the fallback's primary-name proxy).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from anyllm.base import ProviderName
from anyllm.errors import AnyLLMError
from anyllm.providers import (
    AnthropicApiAdapter,
    ClaudeCodeCliAdapter,
    ClaudeCodeSdkAdapter,
    OpenAICompatibleAdapter,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from anyllm.base import Completion, LLMProvider, PromptParts

DEFAULT_PROVIDER = ProviderName.CLAUDE_CODE_CLI

# A sensible default priority for auto-selection: subscription-billed backends
# first (flat cost — the cost guard lets any model through there), metered ones
# last. A host with its own cost/deployment policy passes its own order; this is
# only the "I don't care, pick something reasonable" default.
DEFAULT_ORDER: tuple[ProviderName, ...] = (
    ProviderName.CLAUDE_CODE_CLI,
    ProviderName.CLAUDE_CODE_SDK,
    ProviderName.ANTHROPIC_API,
    ProviderName.OPENAI_COMPATIBLE,
)

_KNOWN = tuple(ProviderName)


def build_adapter(provider: str, config: dict | None = None) -> LLMProvider:
    """Return the configured backend, or raise :class:`AnyLLMError` if it is unusable.

    ``provider`` is any of :class:`~anyllm.base.ProviderName`'s values — callers may pass
    the enum member or the equivalent plain string (a ``StrEnum`` compares equal to its
    value), since config commonly arrives as a bare string from a registry file or env.
    ``config`` holds the provider's options (e.g.
    ``{"anthropic_api": {"api_key_env": ...}}`` or
    ``{"openai_compatible": {"base_url": ..., "default_model": ...}}``). Raises if
    the name is unknown, or if the built backend is not available on this machine.
    """
    cfg = config or {}
    if provider == ProviderName.CLAUDE_CODE_CLI:
        adapter: LLMProvider = ClaudeCodeCliAdapter()
    elif provider == ProviderName.CLAUDE_CODE_SDK:
        adapter = ClaudeCodeSdkAdapter()
    elif provider == ProviderName.ANTHROPIC_API:
        raw = cfg.get("anthropic_api")
        api_cfg: dict = raw if isinstance(raw, dict) else {}
        adapter = AnthropicApiAdapter(api_key_env=str(api_cfg.get("api_key_env", "ANTHROPIC_API_KEY")))
    elif provider == ProviderName.OPENAI_COMPATIBLE:
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


class _FallbackProvider:
    """An :class:`~anyllm.base.LLMProvider` over an ordered list of backends.

    ``complete`` tries each backend in turn: a **retryable** :class:`AnyLLMError`
    advances to the next; anything else (a non-retryable ``AnyLLMError``, a
    :class:`~anyllm.cost.CostViolation`, a programmer error) propagates
    immediately — the fallback recovers from transient backend failure, never
    from a policy refusal. If every backend fails retryably, the last error is
    raised. ``name`` reports the primary (first) backend; ``available`` is true
    if any backend is.

    Never constructed with fewer than two backends — :func:`resolve_provider`
    returns the bare provider for a single candidate, so the wrapper only exists
    when it can actually fall back.
    """

    __slots__ = ("_providers",)

    def __init__(self, providers: Sequence[LLMProvider]) -> None:
        self._providers = tuple(providers)

    @property
    def name(self) -> ProviderName:
        return self._providers[0].name

    def available(self) -> bool:
        return any(p.available() for p in self._providers)

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
        last: AnyLLMError | None = None
        for provider in self._providers:
            try:
                return await provider.complete(
                    user=user,
                    system=system,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    thinking_disabled=thinking_disabled,
                    parts=parts,
                )
            except AnyLLMError as exc:
                if not exc.retryable:
                    raise
                last = exc
        # Every candidate failed retryably. Re-raise the last transient error.
        assert last is not None  # noqa: S101 — the loop ran ≥2 times (see class invariant); last is set.
        raise last


def resolve_provider(
    order: Sequence[ProviderName | str] = DEFAULT_ORDER,
    config: dict | None = None,
    *,
    wrap: Callable[[LLMProvider], LLMProvider] | None = None,
    fallback: bool = True,
) -> LLMProvider | None:
    """Resolve an ordered candidate list into one usable provider, or ``None``.

    Walks ``order``, building each candidate via :func:`build_adapter` and
    dropping the ones this machine cannot build or run (an unavailable backend, a
    missing key — both surface as :class:`AnyLLMError` and are skipped). The
    surviving backends are returned as:

    - ``None`` — nothing in ``order`` is usable (the host shapes its own
      no-provider error);
    - the bare provider — exactly one survivor (no wrapper, nothing to fall back
      to);
    - a runtime-fallback provider — two or more survivors and ``fallback`` is
      true (the default); with ``fallback=False`` the first survivor is returned
      and the rest ignored (construction-time selection only).

    ``wrap`` is applied to **each** surviving backend before composition — this
    is where a host attaches per-backend concerns (most importantly
    :func:`~anyllm.cost.with_cost_guard`, so the guard keys on each real backend
    id rather than the fallback's primary-name proxy). ``config`` is threaded to
    every :func:`build_adapter` call (see its docstring for the shape).
    """
    built: list[LLMProvider] = []
    for name in order:
        try:
            provider = build_adapter(str(name), config)
        except AnyLLMError:
            continue
        built.append(wrap(provider) if wrap is not None else provider)
    if not built:
        return None
    if len(built) == 1 or not fallback:
        return built[0]
    return _FallbackProvider(built)


__all__ = ["DEFAULT_ORDER", "DEFAULT_PROVIDER", "build_adapter", "resolve_provider"]
