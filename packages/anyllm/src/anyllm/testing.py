"""Test helper: make the machine's LLM access invisible to a test.

A suite that reads whether the developer's machine has a provider (an API key in the shell, a
logged-in Claude Code) is green on a laptop and red on a bare runner with no code difference.
:func:`hermetic_llm_env` removes the provider variables and reports the two subscription
backends unavailable, so a test that wants a provider configures its own.

It establishes only that: the named variables are absent and the two CLI-backed adapters say
unavailable. A new adapter with its own probe passes straight through; add it here. Does not
import pytest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, Protocol

from anyllm.providers.claude_code_cli import ClaudeCodeCliAdapter
from anyllm.providers.claude_code_sdk import ClaudeCodeSdkAdapter

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["SCRUBBED_ENV", "hermetic_llm_env"]

#: Variables a backend reads to find a provider.
SCRUBBED_ENV: Final = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "CLAUDE_CODE_OAUTH_TOKEN",
)


class _Patch(Protocol):
    """The part of ``pytest.MonkeyPatch`` this module uses."""

    def delenv(self, name: str, raising: bool = ...) -> None: ...  # noqa: FBT001 — MonkeyPatch's own signature
    def setattr(self, target: Any, name: str, value: Any, raising: bool = ...) -> None: ...  # noqa: FBT001


def _unavailable(_self: object) -> bool:
    return False


def hermetic_llm_env(monkeypatch: _Patch, *, extra_env: Iterable[str] = ()) -> None:
    """Remove :data:`SCRUBBED_ENV` and ``extra_env`` (a consumer's own key names), and make the
    Claude Code CLI and SDK adapters report unavailable."""
    for name in (*SCRUBBED_ENV, *extra_env):
        monkeypatch.delenv(name, raising=False)
    # raising=True: if either adapter loses `available`, this fails instead of reopening the hole.
    monkeypatch.setattr(ClaudeCodeCliAdapter, "available", _unavailable)
    monkeypatch.setattr(ClaudeCodeSdkAdapter, "available", _unavailable)
