"""Codex CLI completions supervised by the optional any-agent extra."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, get_args

from child_env import build_env

from anyllm.base import Completion, Effort, ProviderName
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
    from typing import Any

    from anyllm.base import PromptParts


def _write_schema(directory: str, schema: Mapping[str, Any]) -> str:
    path = Path(directory) / "schema.json"
    path.write_text(json.dumps(schema), encoding="utf-8")
    return str(path)


class CodexCliAdapter:
    """Run CodexHarness and fail loud on any CLI failure."""

    name = ProviderName.CODEX_CLI
    supports_structured = True  # response_schema and effort: see anyllm.base.StructuredProvider

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
        response_schema: Mapping[str, Any] | None = None,
        effort: Effort | None = None,
    ) -> Completion:
        """Complete once; max_tokens, temperature and thinking_disabled are not CLI knobs.

        ``response_schema``: codex enforces it (`--output-schema`), so ``Completion.text`` is schema-valid JSON text. ``effort``:
        the reasoning effort; ``None`` keeps ``low``. Cancelling the await kills the child's process group.
        """
        del max_tokens, temperature, thinking_disabled
        if effort is not None and effort not in get_args(Effort):
            msg = f"unknown effort {effort!r}"
            raise AnyLLMError(msg, retryable=False, hint=f"use one of {get_args(Effort)}")
        if any_agent is None:
            msg = "any-agent is not installed"
            raise AnyLLMError(msg, retryable=False, hint="install anyllm[agent]")
        exe = program("codex", self._env)
        if exe is None:
            msg = "codex CLI not found on PATH"
            raise AnyLLMError(msg, retryable=False, hint="install Codex or pick another provider")
        prompt = "\n\n".join(p for p in (flat_system(parts, system), flat_user(parts, user)) if p)
        with tempfile.TemporaryDirectory(prefix="anyllm-codex-schema-") as schema_dir:  # the schema file goes with it
            schema_path = _write_schema(schema_dir, response_schema) if response_schema is not None else None
            inputs = any_agent.LaunchInputs(
                exe=str(exe),
                cwd="",  # sealed: the harness runs the child in its own empty directory
                model=model or "",
                effort=effort or "low",
                prompt=prompt,
                env=build_env(self._env, allow=CODEX_ENV),
                schema=schema_path,
                sealed=True,
            )
            harness = any_agent.CodexHarness(env=self._env)
            return await complete_run(any_agent, harness, harness.launch_spec(inputs), model or "")


__all__ = ["CodexCliAdapter"]
