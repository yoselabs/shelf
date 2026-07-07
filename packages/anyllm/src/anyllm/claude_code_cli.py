"""claude-code-cli adapter — subscription-billed `claude -p` (ADR 0019).

Non-negotiable safety rules (the #37686 footgun silently bills the API):
- scrub ``ANTHROPIC_API_KEY`` from the child env,
- never pass ``--bare`` (it forces API-key auth),
- request/parse only ``--output-format json``,
- fail loudly on non-zero / auth / credit exhaustion — NEVER fall back to API.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from anyllm.errors import AnyLLMError

_CLI = "claude"


def build_argv(prompt: str, model: str | None) -> list[str]:
    """Construct the CLI argv. ``--bare`` is intentionally never present."""
    argv = [_CLI, "-p", prompt, "--output-format", "json"]
    if model:
        argv += ["--model", model]
    return argv


def child_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Return the child env with ANTHROPIC_API_KEY scrubbed (subscription, not API)."""
    env = dict(os.environ if base_env is None else base_env)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


class ClaudeCodeCliAdapter:
    """LLM adapter shelling out to subscription-billed ``claude -p``, never the API."""

    name = "claude-code-cli"

    def available(self) -> bool:
        """Report whether the ``claude`` CLI is present on PATH."""
        return shutil.which(_CLI) is not None

    def complete(self, prompt: str, *, model: str | None = None) -> str:
        """Run ``claude -p`` for ``prompt`` and return the parsed completion text."""
        if not self.available():
            msg = "claude CLI not found on PATH"
            raise AnyLLMError(msg, retryable=False, hint="install Claude Code or pick another provider")
        argv = build_argv(prompt, model)
        try:
            proc = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                env=child_env(),
            )
        except OSError as exc:  # pragma: no cover - exec failure
            msg = f"failed to invoke claude CLI: {exc}"
            raise AnyLLMError(msg, retryable=False) from exc
        if proc.returncode != 0:
            # Fail loud — do NOT retry against the billed API.
            msg = f"claude CLI exited {proc.returncode}: {proc.stderr.strip()[:300]}"
            raise AnyLLMError(
                msg,
                retryable=False,
                hint="check `claude` auth / subscription credit; this adapter never falls back to the billed API",
            )
        return _parse_result(proc.stdout)


def _parse_result(stdout: str) -> str:
    """Pull the completion text from the `--output-format json` envelope."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        msg = f"claude CLI returned non-JSON output: {stdout[:200]!r}"
        raise AnyLLMError(msg, retryable=False) from exc
    if isinstance(payload, dict) and isinstance(payload.get("result"), str):
        return payload["result"]
    raise AnyLLMError(f"claude CLI JSON lacked a string `result`: {payload!r}"[:300], retryable=False)


__all__ = ["ClaudeCodeCliAdapter", "build_argv", "child_env"]
