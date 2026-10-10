"""anyllm.testing, stated as Gherkin."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from anyllm import resolve_provider
from anyllm.providers import ClaudeCodeCliAdapter, ClaudeCodeSdkAdapter, OpenAICompatibleAdapter
from anyllm.testing import hermetic_llm_env
from pytest_bdd import given, parsers, scenarios, then, when

if TYPE_CHECKING:
    import pytest

scenarios("features/hermetic_llm_env.feature")


def _names(text: str) -> list[str]:
    return [part.strip(' "') for part in text.replace(" and ", ", ").split(",")]


@given(parsers.parse("the shell holds {names}"))
def _shell(monkeypatch: pytest.MonkeyPatch, names: str) -> None:
    for name in _names(names.removeprefix("the consumer's own key ")):
        monkeypatch.setenv(name, "from-the-shell")


@given("the hermetic LLM env is applied")
def _applied(monkeypatch: pytest.MonkeyPatch) -> None:
    hermetic_llm_env(monkeypatch)


@when(parsers.parse('the hermetic LLM env is applied naming "{name}"'))
def _applied_naming(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    hermetic_llm_env(monkeypatch, extra_env=[name])


@when(parsers.parse('the test sets "{name}"'))
def _sets(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv(name, "configured-by-the-test")


@then("none of those variables is set")
def _none_set() -> None:
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ACME_LLM_KEY"):
        assert name not in os.environ


@then("the Claude Code CLI and SDK backends report unavailable")
def _unavailable() -> None:
    assert ClaudeCodeCliAdapter().available() is False
    assert ClaudeCodeSdkAdapter().available() is False


@then("no provider is selected")
def _none_selected() -> None:
    assert resolve_provider() is None


@then("the openai-compatible backend reports available")
def _openai_available() -> None:
    assert OpenAICompatibleAdapter().available() is True
