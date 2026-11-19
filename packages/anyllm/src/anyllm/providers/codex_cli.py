"""Codex CLI completions supervised by the optional any-agent extra."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from child_env import build_env

from anyllm.base import Completion, ProviderName
from anyllm.errors import AnyLLMError
from anyllm.providers._agent import complete_run
from anyllm.providers._child import CODEX_ENV, program
from anyllm.providers._prompt import flat_system, flat_user

try:
    import any_agent
except ImportError:
    any_agent = None

if TYPE_CHECKING:
    from collections.abc import Mapping

    from anyllm.base import PromptParts


class CodexCliAdapter:
    """Run CodexHarness and fail loud on any CLI failure."""

    name = ProviderName.CODEX_CLI

    def __init__(self, *, env: Mapping[str, str]) -> None:
        self._env = env

    def available(self) -> bool:
        """Whether the extra and the CLI are installed."""
        return any_agent is not None and program("codex", self._env) is not None

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
        """Complete once; max_tokens, temperature and thinking_disabled are not CLI knobs."""
        del max_tokens, temperature, thinking_disabled
        if any_agent is None:
            msg = "any-agent is not installed"
            raise AnyLLMError(msg, retryable=False, hint="install anyllm[agent]")
        exe = program("codex", self._env)
        if exe is None:
            msg = "codex CLI not found on PATH"
            raise AnyLLMError(msg, retryable=False, hint="install Codex or pick another provider")
        harness = any_agent.CodexHarness(env=self._env)
        prompt = "\n\n".join(p for p in (flat_system(parts, system), flat_user(parts, user)) if p)
        inputs = any_agent.LaunchInputs(
            exe=str(exe),
            cwd=str(Path.cwd()),
            model=model or "",
            effort="low",
            prompt=prompt,
            env=build_env(self._env, allow=CODEX_ENV),
            sealed=True,
        )
        return await complete_run(any_agent, harness, harness.launch_spec(inputs), model or "")


__all__ = ["CodexCliAdapter"]
