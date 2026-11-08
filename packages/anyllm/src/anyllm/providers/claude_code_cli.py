"""Subscription-billed Claude completions supervised by the optional any-agent extra."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from anyllm.base import Completion, ProviderName
from anyllm.errors import AnyLLMError
from anyllm.providers._agent import complete_run
from anyllm.providers._prompt import flat_system, flat_user

try:
    import any_agent
except ImportError:
    any_agent = None

if TYPE_CHECKING:
    from anyllm.base import PromptParts


class ClaudeCodeCliAdapter:
    """Run ClaudeHarness without ever falling back to a metered API."""

    name = ProviderName.CLAUDE_CODE_CLI

    def available(self) -> bool:
        """Whether the extra and the CLI are installed."""
        return any_agent is not None and shutil.which("claude") is not None

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
        exe = shutil.which("claude")
        if exe is None:
            msg = "claude CLI not found on PATH"
            raise AnyLLMError(msg, retryable=False, hint="install Claude Code or pick another provider")
        harness = any_agent.ClaudeHarness()
        inputs = any_agent.LaunchInputs(
            exe=exe,
            cwd=str(Path.cwd()),
            model=model or "",
            effort="low",
            prompt=flat_user(parts, user),
            system=flat_system(parts, system),
            env=dict(os.environ),
        )
        launch = harness.launch_spec(inputs)
        # The completion surface consumes one JSON result, not an interactive agent stream.
        argv = [exe, "-p", "--output-format", "json", "--tools", "", "--strict-mcp-config"]
        if inputs.system:
            argv += ["--append-system-prompt", inputs.system]
        if model:
            argv += ["--model", model]
        spec = any_agent.LaunchSpec(argv=argv, env=launch.env, cwd=launch.cwd, stdin=launch.stdin)
        result = await complete_run(any_agent, harness, spec, model or "")
        envelope = harness.evidence.final
        if envelope is None or not isinstance(envelope.get("result"), str):
            msg = "claude CLI JSON lacked a string `result`"
            raise AnyLLMError(msg, retryable=False)
        return result


__all__ = ["ClaudeCodeCliAdapter"]
