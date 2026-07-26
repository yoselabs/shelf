"""Acceptance suite for anyllm.cost — the pre-spend cost guard.

Asserts the default policy's allow/deny decisions (keyed on ProviderName) and
that the guarded provider raises BEFORE issuing the underlying `complete()` — the
structural "impossible to bill by accident" guarantee.
"""

from __future__ import annotations

import pytest
from anyllm import Completion, ProviderName
from anyllm.cost import (
    DEFAULT_COST_POLICY,
    CostViolation,
    assert_within_budget,
    with_cost_guard,
)


class _FakeProvider:
    """Minimal anyllm-shaped LLMProvider that records whether it was called."""

    default_model = ""

    def __init__(self, name: ProviderName) -> None:
        self.name = name
        self.called = False

    async def complete(self, **kwargs: object) -> Completion:
        self.called = True
        return Completion(text="OK", model=str(kwargs.get("model") or ""))

    def available(self) -> bool:
        return True


@pytest.mark.parametrize(
    ("provider", "model", "allowed"),
    [
        # Subscription backends (flat cost) — any model is fine.
        (ProviderName.CLAUDE_CODE_CLI, "claude-opus-4-8", True),
        (ProviderName.CLAUDE_CODE_SDK, "claude-sonnet-4-6", True),
        (ProviderName.CLAUDE_CODE_SDK, "claude-opus-4-8", True),
        # Metered anthropic-api — cheap models only.
        (ProviderName.ANTHROPIC_API, "claude-haiku-4-5-20251001", True),
        (ProviderName.ANTHROPIC_API, "claude-sonnet-4-6", False),  # the $20 case
        (ProviderName.ANTHROPIC_API, "claude-opus-4-8", False),
        # openai-compatible — conservative cheap allowlist, expensive denied.
        (ProviderName.OPENAI_COMPATIBLE, "gpt-4o-mini", True),
        (ProviderName.OPENAI_COMPATIBLE, "llama-3.1-8b-instruct", True),
        (ProviderName.OPENAI_COMPATIBLE, "gpt-4o", False),
        (ProviderName.OPENAI_COMPATIBLE, "gpt-4-turbo", False),
        # Bare string values compare equal (StrEnum) — the same decisions hold.
        ("anthropic-api", "claude-sonnet-4-6", False),
        ("claude-code-sdk", "claude-opus-4-8", True),
        # An unknown provider — denied (fail loud, opt in deliberately).
        ("mystery-provider", "some-cheap-model", False),
    ],
)
def test_default_policy_allow_deny(provider: ProviderName | str, model: str, allowed: bool) -> None:
    assert DEFAULT_COST_POLICY.permits(provider, model) is allowed
    if allowed:
        assert_within_budget(provider, model)  # no raise
    else:
        with pytest.raises(CostViolation):
            assert_within_budget(provider, model)


async def test_guard_raises_before_calling_inner() -> None:
    """A denied pair raises CostViolation and the inner provider is never called."""
    inner = _FakeProvider(ProviderName.ANTHROPIC_API)
    guarded = with_cost_guard(inner)

    with pytest.raises(CostViolation):
        await guarded.complete(user="hi", model="claude-sonnet-4-6")

    assert inner.called is False, "denied pair must not reach the network call"


async def test_guard_delegates_on_allowed_pair() -> None:
    inner = _FakeProvider(ProviderName.CLAUDE_CODE_SDK)
    guarded = with_cost_guard(inner)

    result = await guarded.complete(user="hi", model="claude-sonnet-4-6")

    assert result.text == "OK"
    assert inner.called is True


async def test_guard_forwards_attributes_and_available() -> None:
    inner = _FakeProvider(ProviderName.ANTHROPIC_API)
    inner.default_model = "claude-haiku-4-5-20251001"
    guarded = with_cost_guard(inner)

    # name mirrors the inner provider; default_model forwarded via __getattr__.
    assert guarded.name == ProviderName.ANTHROPIC_API
    assert guarded.default_model == "claude-haiku-4-5-20251001"  # ty: ignore[unresolved-attribute]  # forwarded via __getattr__, not on the Protocol
    assert guarded.available() is True

    # With no explicit model, the inner default_model is what gets asserted —
    # haiku is allowed on anthropic-api, so the call goes through.
    result = await guarded.complete(user="hi")
    assert result.text == "OK"
    assert inner.called is True
