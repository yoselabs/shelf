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
from anyllm.base import Completion
from anyllm.errors import AnyLLMError
from anyllm.providers._prompt import flat_system, flat_user

if TYPE_CHECKING:
    from anyllm.base import PromptParts

_SDK_MODULE = "claude_agent_sdk"


class ClaudeCodeSdkAdapter:
    """Backend running prompts through the user's Claude Code OS session."""

    name = "claude-code-sdk"

    def available(self) -> bool:
        """Report whether ``claude-agent-sdk`` is importable (cheap ``find_spec``, no heavy import)."""
        import importlib.util  # noqa: PLC0415 — lazy: cheap find_spec, avoids importing the ~210MB SDK

        return importlib.util.find_spec(_SDK_MODULE) is not None

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
            msg = "claude-agent-sdk is not installed"
            raise AnyLLMError(msg, retryable=False, hint="install anyllm[claude-code-sdk] or use another backend")
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
