"""Codex CLI completions supervised by the optional any-agent extra."""

from __future__ import annotations

import os
import shutil
import tempfile
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


class CodexCliAdapter:
    """Run CodexHarness and fail loud on any CLI failure."""

    name = ProviderName.CODEX_CLI

    def available(self) -> bool:
        """Whether the extra and the CLI are installed."""
        return any_agent is not None and shutil.which("codex") is not None

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
        exe = shutil.which("codex")
        if exe is None:
            msg = "codex CLI not found on PATH"
            raise AnyLLMError(msg, retryable=False, hint="install Codex or pick another provider")
        harness = any_agent.CodexHarness()
        cli = [exe, "exec", "--sandbox", "read-only", "--skip-git-repo-check"]
        if model:
            cli += ["--model", model]
        prompt = "\n\n".join(p for p in (flat_system(parts, system), flat_user(parts, user)) if p)
        with tempfile.TemporaryDirectory(prefix="anyllm-codex-") as directory:
            inputs = any_agent.LaunchInputs(
                exe=exe,
                cwd=str(Path.cwd()),
                model=model or "",
                effort="low",
                prompt=prompt,
                env={k: v for k, v in os.environ.items() if k not in {"ANTHROPIC_API_KEY", "OPENAI_API_KEY"}},
                cli=cli,
                out_file=str(Path(directory) / "answer.txt"),
            )
            return await complete_run(any_agent, harness, harness.launch_spec(inputs), model or "")


__all__ = ["CodexCliAdapter"]
