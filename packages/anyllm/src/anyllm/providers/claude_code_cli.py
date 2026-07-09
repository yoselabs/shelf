"""claude-code-cli backend — subscription-billed ``claude -p`` (async subprocess).

Zero extra deps (stdlib subprocess), so it is the featherweight default backend.
Non-negotiable safety rules (the #37686 footgun silently bills the API):
- scrub ``ANTHROPIC_API_KEY`` from the child env,
- never pass ``--bare`` (it forces API-key auth),
- request/parse only ``--output-format json``,
- fail loudly on non-zero / auth / credit exhaustion — NEVER fall back to the API.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from typing import TYPE_CHECKING

from anyllm.accounting import extract_token_counts
from anyllm.base import Completion, ProviderName
from anyllm.errors import AnyLLMError
from anyllm.providers._prompt import flat_system, flat_user

if TYPE_CHECKING:
    from anyllm.base import PromptParts

_CLI = "claude"


def build_argv(prompt: str, model: str | None, *, system: str = "") -> list[str]:
    """Construct the CLI argv. ``--bare`` is intentionally never present."""
    argv = [_CLI, "-p", prompt, "--output-format", "json"]
    if system:
        argv += ["--append-system-prompt", system]
    if model:
        argv += ["--model", model]
    return argv


def child_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Return the child env with ANTHROPIC_API_KEY scrubbed (subscription, not API)."""
    env = dict(os.environ if base_env is None else base_env)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


class ClaudeCodeCliAdapter:
    """Backend shelling out to subscription-billed ``claude -p``, never the API."""

    name = ProviderName.CLAUDE_CODE_CLI

    def available(self) -> bool:
        """Report whether the ``claude`` CLI is present on PATH."""
        return shutil.which(_CLI) is not None

    async def complete(
        self,
        *,
        user: str,
        system: tuple[str, ...] | str = (),
        model: str | None = None,
        max_tokens: int = 1024,  # noqa: ARG002 - the CLI has no max_tokens knob
        temperature: float = 0.0,  # noqa: ARG002 - the CLI has no temperature knob
        thinking_disabled: bool = True,  # noqa: ARG002 - not exposed by the CLI
        parts: PromptParts | None = None,
    ) -> Completion:
        """Run ``claude -p`` and return the parsed :class:`Completion`."""
        if not self.available():
            msg = "claude CLI not found on PATH"
            raise AnyLLMError(msg, retryable=False, hint="install Claude Code or pick another provider")
        argv = build_argv(flat_user(parts, user), model, system=flat_system(parts, system))
        t0 = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=child_env(),
            )
            stdout, stderr = await proc.communicate()
        except OSError as exc:  # pragma: no cover - exec failure
            msg = f"failed to invoke claude CLI: {exc}"
            raise AnyLLMError(msg, retryable=False) from exc
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if proc.returncode != 0:
            # Fail loud — do NOT retry against the billed API.
            msg = f"claude CLI exited {proc.returncode}: {stderr.decode(errors='replace').strip()[:300]}"
            raise AnyLLMError(
                msg,
                retryable=False,
                hint="check `claude` auth / subscription credit; this adapter never falls back to the billed API",
            )
        return _parse_result(stdout.decode(errors="replace"), model or "", latency_ms)


def _parse_result(stdout: str, model: str, latency_ms: int) -> Completion:
    """Pull completion text + best-effort accounting from the ``--output-format json`` envelope."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        msg = f"claude CLI returned non-JSON output: {stdout[:200]!r}"
        raise AnyLLMError(msg, retryable=False) from exc
    if not (isinstance(payload, dict) and isinstance(payload.get("result"), str)):
        raise AnyLLMError(f"claude CLI JSON lacked a string `result`: {payload!r}"[:300], retryable=False)
    prompt_tokens, completion_tokens, _, _ = extract_token_counts(payload.get("usage") or {})
    return Completion(
        text=payload["result"],
        model=str(payload.get("model") or model),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=float(payload.get("total_cost_usd") or 0.0),
        latency_ms=latency_ms,
    )


__all__ = ["ClaudeCodeCliAdapter", "build_argv", "child_env"]
