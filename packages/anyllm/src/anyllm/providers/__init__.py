"""The shipped completion backends. Each implements :class:`~anyllm.base.LLMProvider`."""

from __future__ import annotations

from anyllm.providers.anthropic_api import AnthropicApiAdapter
from anyllm.providers.claude_code_cli import ClaudeCodeCliAdapter, build_argv, child_env
from anyllm.providers.claude_code_sdk import ClaudeCodeSdkAdapter
from anyllm.providers.openai_compatible import OpenAICompatibleAdapter

__all__ = [
    "AnthropicApiAdapter",
    "ClaudeCodeCliAdapter",
    "ClaudeCodeSdkAdapter",
    "OpenAICompatibleAdapter",
    "build_argv",
    "child_env",
]
