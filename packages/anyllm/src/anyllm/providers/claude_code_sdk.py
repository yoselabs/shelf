"""claude-code-sdk backend — the OS session via ``claude-agent-sdk``.

When ``ANTHROPIC_API_KEY`` is unset but Claude Code is logged in (OAuth session
in ``~/.claude``), this backend reaches Haiku/Sonnet through the user's
subscription without a separate API key. Behind the ``anyllm[claude-code-sdk]``
extra (the SDK is ~210MB). Tools/thinking are disabled and ``max_turns=1`` for a
single text completion; host CLAUDE.md / skills / MCP servers / subagents are all
blocked so no personal context leaks into the completion.

Cost + tokens come straight from the SDK's ``ResultMessage`` (Claude Code tracks
usage centrally), so this backend keeps no pricing table.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from anyllm.accounting import extract_token_counts
from anyllm.base import Completion, ProviderName
from anyllm.errors import AnyLLMError
from anyllm.providers._prompt import flat_system, flat_user

if TYPE_CHECKING:
    from anyllm.base import PromptParts

_SDK_MODULE = "claude_agent_sdk"

# Fallback locations the SDK itself searches after `PATH`, mirrored so that
# `available()` agrees with what `complete()` will actually find. Kept in the
# SDK's own order (`_internal/transport/subprocess_cli.py::_find_cli`).
_CLI_FALLBACK_DIRS = (
    "~/.npm-global/bin",
    "/usr/local/bin",
    "~/.local/bin",
    "~/node_modules/.bin",
    "~/.yarn/bin",
    "~/.claude/local",
)


def _cli_name() -> str:
    import platform  # noqa: PLC0415 — lazy: only needed on the availability path

    return "claude.exe" if platform.system() == "Windows" else "claude"


def _find_cli() -> str | None:
    """Locate the Claude Code CLI the SDK would spawn, or None.

    Mirrors the SDK's own resolution order — bundled binary, then ``PATH``, then
    its fixed fallback list — so this probe cannot disagree with what
    ``complete()`` goes on to do. Filesystem-only: no SDK import, no process
    spawn, no network.
    """
    import importlib.util  # noqa: PLC0415 — lazy: cheap find_spec, avoids importing the ~210MB SDK
    import shutil  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    name = _cli_name()

    # 1. Bundled CLI, shipped inside the SDK package itself. Located via the
    #    module spec rather than an import so the ~210MB package stays unloaded.
    spec = importlib.util.find_spec(_SDK_MODULE)
    if spec is None:
        return None
    for root in spec.submodule_search_locations or ():
        bundled = Path(root) / "_bundled" / name
        if bundled.is_file():
            return str(bundled)

    # 2. PATH.
    if found := shutil.which(name):
        return found

    # 3. The SDK's fixed fallback locations.
    for raw in _CLI_FALLBACK_DIRS:
        candidate = Path(raw).expanduser() / name
        if candidate.is_file():
            return str(candidate)
    return None


# Where the CLI keeps an OAuth session, by platform. macOS uses the Keychain;
# Linux (and every container) writes this file.
_CREDENTIALS_FILE = "~/.claude/.credentials.json"
_KEYCHAIN_SERVICE = "Claude Code-credentials"
_OAUTH_TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"  # noqa: S105 — an env var NAME, not a secret


def _session_credentials_present() -> bool:
    """Whether a Claude Code session's credentials exist, without reading them.

    Never decrypts, never prompts, never spawns the CLI. The Keychain branch
    uses a metadata lookup (no ``-w``), which returns an exit code only — asking
    *whether* an item exists is not a secret read, so no auth dialog appears.
    """
    import os  # noqa: PLC0415 — lazy: availability path only
    import platform  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    if os.environ.get(_OAUTH_TOKEN_ENV, "").strip():
        return True
    if Path(_CREDENTIALS_FILE).expanduser().is_file():
        return True
    if platform.system() == "Darwin":
        import shutil  # noqa: PLC0415
        import subprocess  # noqa: PLC0415

        security = shutil.which("security")
        if not security:
            return False
        try:
            return (
                subprocess.run(  # fixed argv, no shell, no user input
                    [security, "find-generic-password", "-s", _KEYCHAIN_SERVICE],
                    capture_output=True,
                    timeout=5,
                    check=False,
                ).returncode
                == 0
            )
        except (OSError, subprocess.SubprocessError):
            return False
    return False


class ClaudeCodeSdkAdapter:
    """Backend running prompts through the user's Claude Code OS session."""

    name = ProviderName.CLAUDE_CODE_SDK

    def available(self) -> bool:
        """Report whether this backend is usable: a CLI plus a session for it.

        Importability alone is not usability. The SDK is a thin wrapper that
        shells out to the ``claude`` binary, and — crucially — recent versions
        **bundle that binary inside the package**, so installing the extra
        installs a runnable CLI. A container therefore has both the package and
        the CLI while having no logged-in session, and every completion comes
        back empty. A caller that ranks backends by ``available()`` would select
        this one forever and never fall through to one that works.

        So the discriminator is authentication, checked without decrypting
        anything: an explicit token, the on-disk credential file (Linux, and any
        container), or the macOS Keychain item's *existence* (a metadata query —
        it does not read the secret and does not prompt). Absence of all three
        with a CLI present is the container shape: unavailable.

        False-negative posture: if a host stores credentials somewhere none of
        these see, this reports unavailable and the caller picks another backend
        — degraded, not broken. That is the safe direction, because the opposite
        error silently shadows every working backend.
        """
        return _find_cli() is not None and _session_credentials_present()

    async def complete(
        self,
        *,
        user: str,
        system: tuple[str, ...] | str = (),
        model: str | None = None,
        max_tokens: int = 1024,  # noqa: ARG002 - SDK exposes no max_tokens knob; usage reported as-is
        temperature: float = 0.0,  # noqa: ARG002 - not exposed by the SDK
        thinking_disabled: bool = True,
        parts: PromptParts | None = None,
    ) -> Completion:
        """Run one prompt through the OS session and return a :class:`Completion`."""
        if not self.available():
            # Name which precondition failed. "Not installed" was the only story
            # this could tell before availability included the session, and it
            # sent operators to reinstall a package that was already present.
            if _find_cli() is None:
                msg = "claude-agent-sdk: no `claude` CLI found to run"
                hint = "install anyllm[claude-code-sdk] (it bundles the CLI), or use another backend"
            else:
                msg = "claude-agent-sdk: a `claude` CLI is present but no logged-in session was found"
                hint = "run `claude` once to log in, set CLAUDE_CODE_OAUTH_TOKEN, or use another backend"
            raise AnyLLMError(msg, retryable=False, hint=hint)
        from claude_agent_sdk import (  # noqa: PLC0415 — lazy: claude-agent-sdk is the optional [claude-code-sdk] extra
            AssistantMessage,
            ClaudeAgentOptions,
            CLIConnectionError,
            CLINotFoundError,
            ResultMessage,
            TextBlock,
            query,
        )

        resolved_model = model or ""
        options = ClaudeAgentOptions(
            **_options_kwargs(model=resolved_model, system=flat_system(parts, system), thinking_disabled=thinking_disabled)
        )
        prompt_str = flat_user(parts, user)

        text_parts: list[str] = []
        result_msg: Any = None
        t0 = time.perf_counter()
        try:
            async for msg in query(prompt=prompt_str, options=options):
                if isinstance(msg, AssistantMessage):
                    if msg.model:
                        resolved_model = msg.model
                    text_parts += [b.text for b in msg.content if isinstance(b, TextBlock)]
                elif isinstance(msg, ResultMessage):
                    result_msg = msg
        except (CLINotFoundError, CLIConnectionError) as exc:
            msg = f"Claude Code CLI unavailable: {exc}"
            raise AnyLLMError(msg, retryable=False, hint="install Claude Code or set ANTHROPIC_API_KEY") from exc
        except Exception as exc:  # SDK/query failure → fail loud (retryable)
            msg = f"claude-agent-sdk query failed: {exc!r}"
            raise AnyLLMError(msg, retryable=True) from exc
        latency_ms = int((time.perf_counter() - t0) * 1000)

        prompt_tokens = completion_tokens = 0
        cost_usd = 0.0
        if result_msg is not None:
            cost_usd = float(result_msg.total_cost_usd or 0.0)
            prompt_tokens, completion_tokens, _, _ = extract_token_counts(result_msg.usage or {})
        return Completion(
            text="".join(text_parts),
            model=resolved_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            raw=_result_raw(result_msg),
        )


def _options_kwargs(*, model: str, system: str, thinking_disabled: bool) -> dict[str, Any]:
    """Build ClaudeAgentOptions kwargs: single-turn pure completion, host context blocked.

    ``system_prompt`` is always an explicit string (``None`` silently loads the
    ~23k-token claude_code preset). ``setting_sources``/``skills``/``mcp_servers``/
    ``agents`` empty block CLAUDE.md discovery, the skill registry, host MCP
    servers (a memory-leak path), and saved subagents.
    """
    from claude_agent_sdk import ThinkingConfigDisabled  # noqa: PLC0415 — lazy: optional [claude-code-sdk] extra

    kwargs: dict[str, Any] = {
        "model": model,
        "tools": [],
        "max_turns": 1,
        "system_prompt": system,
        "setting_sources": [],
        "skills": [],
        "extra_args": {"disable-slash-commands": None},
        "mcp_servers": {},
        "strict_mcp_config": True,
        "agents": {},
    }
    if thinking_disabled:
        kwargs["thinking"] = ThinkingConfigDisabled(type="disabled")
        kwargs["max_thinking_tokens"] = 0
    return {k: v for k, v in kwargs.items() if v is not None}


def _result_raw(result_msg: Any) -> dict[str, Any] | None:
    """Project the SDK ResultMessage into a debug dict (or ``None`` when absent)."""
    if result_msg is None:
        return None
    return {
        "is_error": result_msg.is_error,
        "stop_reason": result_msg.stop_reason,
        "session_id": result_msg.session_id,
        "usage": result_msg.usage,
        "num_turns": getattr(result_msg, "num_turns", None),
    }


__all__ = ["ClaudeCodeSdkAdapter"]
