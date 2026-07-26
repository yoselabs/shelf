"""Acceptance suite for anyllm.select's ordered auto-selection + runtime fallback.

Two layers under test:

- :func:`resolve_provider` — the walk: build each candidate, drop the unusable,
  fold survivors into one provider (bare / runtime-fallback / None).
- ``_FallbackProvider`` — the runtime semantics: a *retryable* failure advances
  to the next backend; anything else (a non-retryable ``AnyLLMError``, a
  ``CostViolation``, a programmer error) propagates. The spend-safety property —
  a budget refusal never falls through to a metered backend — is asserted
  directly, since it is the whole reason the fallback keys on ``retryable``.

Pure orchestration over the ``LLMProvider`` protocol, so it needs no live LLM:
the fakes raise exactly the errors real backends would.
"""

from __future__ import annotations

import pytest
from anyllm import Completion, LLMProvider, ProviderName, resolve_provider
from anyllm.cost import CostViolation
from anyllm.errors import AnyLLMError
from anyllm.select import _FallbackProvider


class _FakeProvider:
    """An anyllm-shaped backend that serves, or raises a scripted error."""

    def __init__(
        self,
        name: ProviderName,
        *,
        available: bool = True,
        raises: Exception | None = None,
    ) -> None:
        self.name = name
        self._available = available
        self._raises = raises
        self.calls = 0

    def available(self) -> bool:
        return self._available

    async def complete(self, **kwargs: object) -> Completion:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return Completion(text=f"served-by-{self.name}", model=str(kwargs.get("model") or ""))


# --------------------------------------------------------------------------- #
# resolve_provider — the walk
# --------------------------------------------------------------------------- #


def _patch_builds(monkeypatch: pytest.MonkeyPatch, table: dict[str, _FakeProvider | AnyLLMError]) -> None:
    """Make build_adapter return/raise per `table` keyed on the provider string."""

    def fake_build(provider: str, config: dict | None = None) -> _FakeProvider:
        _ = config
        outcome = table.get(provider)
        if outcome is None:
            msg = f"unknown {provider!r}"
            raise AnyLLMError(msg)
        if isinstance(outcome, AnyLLMError):
            raise outcome
        return outcome

    monkeypatch.setattr("anyllm.select.build_adapter", fake_build)


def test_resolve_none_when_nothing_usable(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_builds(
        monkeypatch,
        {
            "claude-code-cli": AnyLLMError("no CLI"),
            "anthropic-api": AnyLLMError("no key"),
        },
    )
    assert resolve_provider([ProviderName.CLAUDE_CODE_CLI, ProviderName.ANTHROPIC_API]) is None


def test_resolve_bare_provider_for_single_survivor(monkeypatch: pytest.MonkeyPatch) -> None:
    only = _FakeProvider(ProviderName.ANTHROPIC_API)
    _patch_builds(monkeypatch, {"claude-code-cli": AnyLLMError("no CLI"), "anthropic-api": only})
    resolved = resolve_provider([ProviderName.CLAUDE_CODE_CLI, ProviderName.ANTHROPIC_API])
    assert resolved is only  # no wrapper — nothing to fall back to


def test_resolve_fallback_provider_for_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _FakeProvider(ProviderName.CLAUDE_CODE_CLI)
    second = _FakeProvider(ProviderName.ANTHROPIC_API)
    _patch_builds(monkeypatch, {"claude-code-cli": first, "anthropic-api": second})
    resolved = resolve_provider([ProviderName.CLAUDE_CODE_CLI, ProviderName.ANTHROPIC_API])
    assert isinstance(resolved, _FallbackProvider)
    assert resolved.name == ProviderName.CLAUDE_CODE_CLI  # primary


def test_resolve_fallback_false_returns_first_only(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _FakeProvider(ProviderName.CLAUDE_CODE_CLI)
    second = _FakeProvider(ProviderName.ANTHROPIC_API)
    _patch_builds(monkeypatch, {"claude-code-cli": first, "anthropic-api": second})
    resolved = resolve_provider(
        [ProviderName.CLAUDE_CODE_CLI, ProviderName.ANTHROPIC_API],
        fallback=False,
    )
    assert resolved is first


def test_resolve_applies_wrap_per_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _FakeProvider(ProviderName.CLAUDE_CODE_CLI)
    second = _FakeProvider(ProviderName.ANTHROPIC_API)
    _patch_builds(monkeypatch, {"claude-code-cli": first, "anthropic-api": second})
    wrapped: list[ProviderName] = []

    def wrap(p: LLMProvider) -> LLMProvider:
        wrapped.append(p.name)
        return p

    resolve_provider([ProviderName.CLAUDE_CODE_CLI, ProviderName.ANTHROPIC_API], wrap=wrap)
    assert wrapped == [ProviderName.CLAUDE_CODE_CLI, ProviderName.ANTHROPIC_API]  # each survivor, in order


# --------------------------------------------------------------------------- #
# _FallbackProvider — the runtime semantics
# --------------------------------------------------------------------------- #


async def test_fallback_serves_primary_when_healthy() -> None:
    first = _FakeProvider(ProviderName.CLAUDE_CODE_CLI)
    second = _FakeProvider(ProviderName.ANTHROPIC_API)
    result = await _FallbackProvider([first, second]).complete(user="hi")
    assert result.text == "served-by-claude-code-cli"
    assert second.calls == 0  # second never touched


async def test_fallback_advances_on_retryable() -> None:
    first = _FakeProvider(ProviderName.CLAUDE_CODE_CLI, raises=AnyLLMError("blip", retryable=True))
    second = _FakeProvider(ProviderName.ANTHROPIC_API)
    result = await _FallbackProvider([first, second]).complete(user="hi")
    assert result.text == "served-by-anthropic-api"
    assert first.calls == 1 and second.calls == 1


async def test_fallback_stops_on_non_retryable() -> None:
    first = _FakeProvider(ProviderName.CLAUDE_CODE_CLI, raises=AnyLLMError("fatal", retryable=False))
    second = _FakeProvider(ProviderName.ANTHROPIC_API)
    with pytest.raises(AnyLLMError, match="fatal"):
        await _FallbackProvider([first, second]).complete(user="hi")
    assert second.calls == 0  # a non-retryable failure never advances


async def test_fallback_never_spends_to_recover_on_cost_violation() -> None:
    """The spend-safety invariant: a CostViolation is not an AnyLLMError, so it
    propagates immediately — the fallback never rolls onto a metered backend to
    'recover' from a budget refusal."""
    first = _FakeProvider(ProviderName.CLAUDE_CODE_CLI, raises=CostViolation("over budget"))
    second = _FakeProvider(ProviderName.ANTHROPIC_API)
    with pytest.raises(CostViolation):
        await _FallbackProvider([first, second]).complete(user="hi")
    assert second.calls == 0


async def test_fallback_raises_last_when_all_retryable_fail() -> None:
    first = _FakeProvider(ProviderName.CLAUDE_CODE_CLI, raises=AnyLLMError("blip-1", retryable=True))
    second = _FakeProvider(ProviderName.ANTHROPIC_API, raises=AnyLLMError("blip-2", retryable=True))
    with pytest.raises(AnyLLMError, match="blip-2"):
        await _FallbackProvider([first, second]).complete(user="hi")


def test_fallback_available_is_any() -> None:
    down = _FakeProvider(ProviderName.CLAUDE_CODE_CLI, available=False)
    up = _FakeProvider(ProviderName.ANTHROPIC_API, available=True)
    assert _FallbackProvider([down, up]).available() is True
    both_down = _FallbackProvider(
        [_FakeProvider(ProviderName.CLAUDE_CODE_CLI, available=False), _FakeProvider(ProviderName.ANTHROPIC_API, available=False)]
    )
    assert both_down.available() is False
