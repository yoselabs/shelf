"""The four shipped backends + the select factory + protocol conformance.

No real network / CLI: the async SDK clients and the subprocess are faked. The
point of these tests is the *contract* — fail-loud on failure, a rich
:class:`Completion` on success, and the claude-code-cli safety rules.
"""

from __future__ import annotations

import asyncio
import importlib.util
import platform
import types
from typing import Any

import anthropic
import anyllm.providers.claude_code_sdk as _cc
import openai
import pytest
from anyllm import (
    AnthropicApiAdapter,
    ClaudeCodeCliAdapter,
    ClaudeCodeSdkAdapter,
    LLMProvider,
    OpenAICompatibleAdapter,
    build_adapter,
)
from anyllm.errors import AnyLLMError
from anyllm.providers import claude_code_sdk


# ── anthropic-api (fake async client) ─────────────────────────────────────────
class _Blk:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _AnthropicUsage:
    input_tokens = 12
    cache_creation_input_tokens = 0
    cache_read_input_tokens = 0
    output_tokens = 8


class _AnthropicResp:
    content = (_Blk("hello"),)
    usage = _AnthropicUsage()
    model = "claude-haiku-4-5"


class _FakeAnthropicClient:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self._raises = raises
        self.messages = self

    async def create(self, **_k: Any) -> _AnthropicResp:
        if self._raises is not None:
            raise self._raises
        return _AnthropicResp()


class _FakeAnthropicError(anthropic.APIError):
    # pyrefly: ignore[missing-super-call] — APIError.__init__ demands a request object
    # this fake has no use for; Exception.__init__ is all the test needs.
    def __init__(self, status: int) -> None:
        self.status_code = status
        Exception.__init__(self, f"status {status}")


def test_anthropic_available_reflects_key() -> None:
    assert AnthropicApiAdapter(api_key="k", env={}).available() is True
    assert AnthropicApiAdapter(api_key_env="NOPE_MISSING_KEY", env={}).available() is False
    assert AnthropicApiAdapter(api_key_env="MY_KEY", env={"MY_KEY": "k"}).available() is True


def test_anthropic_missing_key_fails_loud() -> None:
    with pytest.raises(AnyLLMError):
        asyncio.run(AnthropicApiAdapter(api_key_env="NOPE_MISSING_KEY", env={}).complete(user="hi"))


def test_anthropic_happy_maps_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = AnthropicApiAdapter(api_key="k", env={})
    monkeypatch.setattr(adapter, "_client", _FakeAnthropicClient)
    result = asyncio.run(adapter.complete(user="hi", model="claude-haiku-4-5"))
    assert result.text == "hello"
    assert result.model == "claude-haiku-4-5"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 8
    assert result.cost_usd > 0  # haiku is priced


def test_anthropic_api_error_is_fail_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = AnthropicApiAdapter(api_key="k", env={})
    monkeypatch.setattr(adapter, "_client", lambda: _FakeAnthropicClient(raises=_FakeAnthropicError(429)))
    with pytest.raises(AnyLLMError) as exc:
        asyncio.run(adapter.complete(user="hi"))
    assert exc.value.retryable is True  # 429 is transient


def test_anthropic_client_error_not_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = AnthropicApiAdapter(api_key="k", env={})
    monkeypatch.setattr(adapter, "_client", lambda: _FakeAnthropicClient(raises=_FakeAnthropicError(401)))
    with pytest.raises(AnyLLMError) as exc:
        asyncio.run(adapter.complete(user="hi"))
    assert exc.value.retryable is False


# ── openai-compatible (fake async client) ─────────────────────────────────────
class _OaiMsg:
    content = "oai answer"


class _OaiChoice:
    message = _OaiMsg()


class _OaiUsage:
    prompt_tokens = 7
    completion_tokens = 3


class _OaiResp:
    choices = (_OaiChoice(),)
    usage = _OaiUsage()
    model = "gpt-x"


class _FakeOaiClient:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self._raises = raises
        self.chat = self
        self.completions = self

    async def create(self, **_k: Any) -> _OaiResp:
        if self._raises is not None:
            raise self._raises
        return _OaiResp()


class _FakeOaiError(openai.APIError):
    # pyrefly: ignore[missing-super-call] — APIError.__init__ demands a request object
    # this fake has no use for; Exception.__init__ is all the test needs.
    def __init__(self, status: int) -> None:
        self.status_code = status
        Exception.__init__(self, f"status {status}")


def test_openai_available_reflects_key() -> None:
    assert OpenAICompatibleAdapter(env={}).available() is False
    assert OpenAICompatibleAdapter(env={"OPENAI_API_KEY": " "}).available() is False
    assert OpenAICompatibleAdapter(env={"OPENAI_API_KEY": "k"}).available() is True


def test_openai_happy_maps_completion_zero_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = OpenAICompatibleAdapter(default_model="gpt-x", env={})
    monkeypatch.setattr(adapter, "_client", _FakeOaiClient)
    result = asyncio.run(adapter.complete(user="hi"))
    assert result.text == "oai answer"
    assert (result.prompt_tokens, result.completion_tokens) == (7, 3)
    assert result.cost_usd == 0.0  # never guessed for arbitrary endpoints


def test_openai_api_error_is_fail_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = OpenAICompatibleAdapter(default_model="gpt-x", env={})
    monkeypatch.setattr(adapter, "_client", lambda: _FakeOaiClient(raises=_FakeOaiError(503)))
    with pytest.raises(AnyLLMError) as exc:
        asyncio.run(adapter.complete(user="hi"))
    assert exc.value.retryable is True


# ── claude-code-sdk (fake module surface) ─────────────────────────────────────
def test_sdk_unavailable_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ClaudeCodeSdkAdapter(env={})
    monkeypatch.setattr(adapter, "available", lambda: False)
    with pytest.raises(AnyLLMError):
        asyncio.run(adapter.complete(user="hi"))


def test_sdk_options_kwargs_block_host_context() -> None:
    kwargs = claude_code_sdk._options_kwargs(model="m", system="sys", thinking_disabled=True)
    assert kwargs["tools"] == []
    assert kwargs["max_turns"] == 1
    assert kwargs["system_prompt"] == "sys"  # explicit — None would load the preset
    assert kwargs["mcp_servers"] == {}  # host MCP servers blocked (memory-leak path)
    assert kwargs["agents"] == {}
    assert "thinking" in kwargs


def test_sdk_result_raw_projection() -> None:
    assert claude_code_sdk._result_raw(None) is None

    class _RM:
        is_error = False
        stop_reason = "end_turn"
        session_id = "sess"
        usage = {"input_tokens": 1}  # noqa: RUF012
        num_turns = 1

    raw = claude_code_sdk._result_raw(_RM())
    assert raw is not None
    assert raw["stop_reason"] == "end_turn"


def test_sdk_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import claude_agent_sdk as sdk  # noqa: PLC0415 — local: fake the SDK surface only for this test

    class FakeText:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeAssistant:
        def __init__(self) -> None:
            self.model = "claude-haiku-4-5"
            self.content = [FakeText("sdk answer")]

    class FakeResult:
        total_cost_usd = 0.01
        usage = {"input_tokens": 4, "output_tokens": 2}  # noqa: RUF012
        is_error = False
        stop_reason = "end_turn"
        session_id = "s"
        num_turns = 1

    async def fake_query(*, prompt: str, options: Any):
        yield FakeAssistant()
        yield FakeResult()

    monkeypatch.setattr(sdk, "AssistantMessage", FakeAssistant)
    monkeypatch.setattr(sdk, "ResultMessage", FakeResult)
    monkeypatch.setattr(sdk, "TextBlock", FakeText)
    monkeypatch.setattr(sdk, "query", fake_query)

    adapter = ClaudeCodeSdkAdapter(env={})
    monkeypatch.setattr(adapter, "available", lambda: True)
    result = asyncio.run(adapter.complete(user="hi", model="claude-haiku-4-5"))
    assert result.text == "sdk answer"
    assert result.cost_usd == 0.01
    assert result.prompt_tokens == 4


# ── select factory + protocol conformance ─────────────────────────────────────
def test_build_adapter_unknown_provider() -> None:
    with pytest.raises(AnyLLMError) as exc:
        build_adapter("gpt-9000", env={})
    assert "unknown LLM provider" in str(exc.value)


def test_build_adapter_unavailable_raises() -> None:
    with pytest.raises(AnyLLMError):
        build_adapter("openai-compatible", env={})


def test_build_adapter_returns_available() -> None:
    adapter = build_adapter("anthropic-api", env={"ANTHROPIC_API_KEY": "k"})
    assert adapter.name == "anthropic-api"


def test_all_backends_satisfy_protocol() -> None:
    for adapter in (
        ClaudeCodeCliAdapter(env={}),
        ClaudeCodeSdkAdapter(env={}),
        AnthropicApiAdapter(env={}),
        OpenAICompatibleAdapter(env={}),
    ):
        assert isinstance(adapter, LLMProvider)


# --------------------------------------------------------------------- #
# ClaudeCodeSdkAdapter.available() — usable, not merely importable
#
# The SDK shells out to the `claude` binary on every completion, so package
# importability alone is a false positive: a container that installs the Python
# extra without the CLI would be selected by an availability-ranked chooser and
# then fail every call, never falling through to a backend that works.
# --------------------------------------------------------------------- #


def test_claude_code_available_needs_cli_and_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_cc, "_find_cli", lambda _env: "/usr/local/bin/claude")
    monkeypatch.setattr(_cc, "_session_credentials_present", lambda _env: True)
    assert ClaudeCodeSdkAdapter(env={}).available() is True


def test_claude_code_unavailable_when_cli_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_cc, "_find_cli", lambda _env: None)
    monkeypatch.setattr(_cc, "_session_credentials_present", lambda _env: True)
    assert ClaudeCodeSdkAdapter(env={}).available() is False


def test_claude_code_unavailable_when_cli_bundled_but_no_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """The container shape: the extra bundles a runnable CLI, but nobody is logged in."""
    monkeypatch.setattr(_cc, "_find_cli", lambda _env: "/site-packages/claude_agent_sdk/_bundled/claude")
    monkeypatch.setattr(_cc, "_session_credentials_present", lambda _env: False)
    assert ClaudeCodeSdkAdapter(env={}).available() is False


def test_session_credentials_from_env_token() -> None:
    assert _cc._session_credentials_present({"CLAUDE_CODE_OAUTH_TOKEN": "tok"}) is True


def test_session_credentials_from_file(tmp_path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / ".credentials.json").write_text("{}")
    assert _cc._session_credentials_present({"HOME": str(tmp_path)}) is True


def test_session_credentials_absent_on_linux_container(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """No token, no credential file, non-Darwin -> no session."""
    monkeypatch.setattr(_cc, "_system", lambda: "Linux")
    assert _cc._session_credentials_present({"HOME": str(tmp_path)}) is False
    assert _cc._session_credentials_present({}) is False


def test_the_platform_is_read_in_one_place(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    assert _cc._cli_name() == "claude.exe"
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    assert _cc._cli_name() == "claude"


def test_find_cli_returns_none_when_sdk_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """No SDK -> no bundled binary to find, and nothing to spawn."""
    monkeypatch.setattr(importlib.util, "find_spec", lambda *a, **k: None)
    assert _cc._find_cli({"PATH": "/usr/bin"}) is None


def _no_bundled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide the SDK's bundled CLI so PATH/fallback ordering can be tested."""
    monkeypatch.setattr(importlib.util, "find_spec", lambda *a, **k: types.SimpleNamespace(submodule_search_locations=[]))


def _exe(folder, name="claude"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("#!/bin/sh\n")
    (folder / name).chmod(0o755)
    return str(folder / name)


def test_find_cli_prefers_path_over_fallback_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _no_bundled(monkeypatch)
    monkeypatch.setattr(_cc, "_CLI_FALLBACK_DIRS", (str(tmp_path / "fallback"),))
    _exe(tmp_path / "fallback")
    on_path = _exe(tmp_path / "bin")
    assert _cc._find_cli({"PATH": str(tmp_path / "bin")}) == on_path


def test_find_cli_uses_fallback_dirs_when_not_on_path(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """A CLI outside PATH is still found; a `~` folder is the injected HOME's, not the process's."""
    _no_bundled(monkeypatch)
    monkeypatch.setattr(_cc, "_CLI_FALLBACK_DIRS", ("~/.claude/local",))
    fallback = _exe(tmp_path / ".claude" / "local")
    assert _cc._find_cli({"PATH": "", "HOME": str(tmp_path)}) == fallback
    assert _cc._find_cli({"PATH": ""}) is None  # no HOME injected: the ~ folder is not guessed


def test_find_cli_never_consults_the_process_path(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _no_bundled(monkeypatch)
    monkeypatch.setattr(_cc, "_CLI_FALLBACK_DIRS", ())
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    _exe(tmp_path / "bin")
    assert _cc._find_cli({"PATH": ""}) is None
