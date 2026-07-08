"""The four shipped backends + the select factory + protocol conformance.

No real network / CLI: the async SDK clients and the subprocess are faked. The
point of these tests is the *contract* — fail-loud on failure, a rich
:class:`Completion` on success, and the claude-code-cli safety rules.
"""

from __future__ import annotations

import asyncio
from typing import Any

import anthropic
import openai
import pytest
from anyllm import (
    AnthropicApiAdapter,
    ClaudeCodeCliAdapter,
    ClaudeCodeSdkAdapter,
    Completion,
    LLMProvider,
    OpenAICompatibleAdapter,
    build_adapter,
    build_argv,
    child_env,
)
from anyllm.errors import AnyLLMError
from anyllm.providers import claude_code_cli, claude_code_sdk


# ── claude-code-cli safety rules (pure) ───────────────────────────────────────
def test_argv_has_json_format_and_model_no_bare() -> None:
    argv = build_argv("hello", "claude-sonnet-4-6")
    assert argv[argv.index("--output-format") + 1] == "json"
    assert "--model" in argv
    assert "--bare" not in argv  # non-negotiable: never force API-key auth


def test_argv_appends_system_prompt() -> None:
    argv = build_argv("hi", None, system="be terse")
    assert argv[argv.index("--append-system-prompt") + 1] == "be terse"
    assert "--model" not in argv
    assert "--bare" not in argv


def test_child_env_scrubs_anthropic_api_key() -> None:
    env = child_env({"ANTHROPIC_API_KEY": "sk-secret", "PATH": "/usr/bin"})
    assert "ANTHROPIC_API_KEY" not in env  # the #37686 footgun
    assert env["PATH"] == "/usr/bin"


# ── claude-code-cli complete (fake subprocess) ────────────────────────────────
class _FakeProc:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self._out = stdout.encode()
        self._err = stderr.encode()

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._out, self._err


def _patch_subprocess(monkeypatch: pytest.MonkeyPatch, proc: _FakeProc) -> None:
    async def _fake_exec(*_a: Any, **_k: Any) -> _FakeProc:
        return proc

    monkeypatch.setattr(claude_code_cli.asyncio, "create_subprocess_exec", _fake_exec)


def test_cli_fails_loud_on_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ClaudeCodeCliAdapter()
    monkeypatch.setattr(adapter, "available", lambda: True)
    _patch_subprocess(monkeypatch, _FakeProc(1, "", "credit exhausted"))
    with pytest.raises(AnyLLMError) as exc:
        asyncio.run(adapter.complete(user="hi", model="m"))
    assert "exited 1" in str(exc.value)
    assert exc.value.retryable is False  # never retry against the billed API


def test_cli_parses_json_result_with_accounting(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ClaudeCodeCliAdapter()
    monkeypatch.setattr(adapter, "available", lambda: True)
    stdout = (
        '{"result": "summary", "model": "claude-haiku-4-5", "total_cost_usd": 0.002, "usage": {"input_tokens": 10, "output_tokens": 5}}'
    )
    _patch_subprocess(monkeypatch, _FakeProc(0, stdout, ""))
    result = asyncio.run(adapter.complete(user="hi"))
    assert isinstance(result, Completion)
    assert result.text == "summary"
    assert result.cost_usd == 0.002
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5


def test_cli_fails_on_non_json(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ClaudeCodeCliAdapter()
    monkeypatch.setattr(adapter, "available", lambda: True)
    _patch_subprocess(monkeypatch, _FakeProc(0, "not json", ""))
    with pytest.raises(AnyLLMError):
        asyncio.run(adapter.complete(user="hi"))


def test_cli_missing_raises_before_running(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ClaudeCodeCliAdapter()
    monkeypatch.setattr(adapter, "available", lambda: False)
    with pytest.raises(AnyLLMError):
        asyncio.run(adapter.complete(user="hi"))


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
    def __init__(self, status: int) -> None:
        self.status_code = status
        Exception.__init__(self, f"status {status}")


def test_anthropic_available_reflects_key() -> None:
    assert AnthropicApiAdapter(api_key="k").available() is True
    assert AnthropicApiAdapter(api_key_env="NOPE_MISSING_KEY").available() is False


def test_anthropic_missing_key_fails_loud() -> None:
    with pytest.raises(AnyLLMError):
        asyncio.run(AnthropicApiAdapter(api_key_env="NOPE_MISSING_KEY").complete(user="hi"))


def test_anthropic_happy_maps_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = AnthropicApiAdapter(api_key="k")
    monkeypatch.setattr(adapter, "_client", _FakeAnthropicClient)
    result = asyncio.run(adapter.complete(user="hi", model="claude-haiku-4-5"))
    assert result.text == "hello"
    assert result.model == "claude-haiku-4-5"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 8
    assert result.cost_usd > 0  # haiku is priced


def test_anthropic_api_error_is_fail_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = AnthropicApiAdapter(api_key="k")
    monkeypatch.setattr(adapter, "_client", lambda: _FakeAnthropicClient(raises=_FakeAnthropicError(429)))
    with pytest.raises(AnyLLMError) as exc:
        asyncio.run(adapter.complete(user="hi"))
    assert exc.value.retryable is True  # 429 is transient


def test_anthropic_client_error_not_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = AnthropicApiAdapter(api_key="k")
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
    def __init__(self, status: int) -> None:
        self.status_code = status
        Exception.__init__(self, f"status {status}")


def test_openai_available_reflects_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert OpenAICompatibleAdapter().available() is False
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert OpenAICompatibleAdapter().available() is True


def test_openai_happy_maps_completion_zero_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = OpenAICompatibleAdapter(default_model="gpt-x")
    monkeypatch.setattr(adapter, "_client", _FakeOaiClient)
    result = asyncio.run(adapter.complete(user="hi"))
    assert result.text == "oai answer"
    assert (result.prompt_tokens, result.completion_tokens) == (7, 3)
    assert result.cost_usd == 0.0  # never guessed for arbitrary endpoints


def test_openai_api_error_is_fail_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = OpenAICompatibleAdapter(default_model="gpt-x")
    monkeypatch.setattr(adapter, "_client", lambda: _FakeOaiClient(raises=_FakeOaiError(503)))
    with pytest.raises(AnyLLMError) as exc:
        asyncio.run(adapter.complete(user="hi"))
    assert exc.value.retryable is True


# ── claude-code-sdk (fake module surface) ─────────────────────────────────────
def test_sdk_unavailable_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ClaudeCodeSdkAdapter()
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

    adapter = ClaudeCodeSdkAdapter()
    monkeypatch.setattr(adapter, "available", lambda: True)
    result = asyncio.run(adapter.complete(user="hi", model="claude-haiku-4-5"))
    assert result.text == "sdk answer"
    assert result.cost_usd == 0.01
    assert result.prompt_tokens == 4


# ── select factory + protocol conformance ─────────────────────────────────────
def test_build_adapter_unknown_provider() -> None:
    with pytest.raises(AnyLLMError) as exc:
        build_adapter("gpt-9000")
    assert "unknown LLM provider" in str(exc.value)


def test_build_adapter_unavailable_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AnyLLMError):
        build_adapter("openai-compatible")


def test_build_adapter_returns_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    adapter = build_adapter("anthropic-api")
    assert adapter.name == "anthropic-api"


def test_all_backends_satisfy_protocol() -> None:
    for adapter in (ClaudeCodeCliAdapter(), ClaudeCodeSdkAdapter(), AnthropicApiAdapter(), OpenAICompatibleAdapter()):
        assert isinstance(adapter, LLMProvider)
