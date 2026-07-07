"""anyllm adapter safety rules — the two shipped backends."""

from __future__ import annotations

import subprocess

import httpx
import pytest
from anyllm import AnthropicApiAdapter, ClaudeCodeCliAdapter, anthropic_api, build_argv, child_env
from anyllm.errors import AnyLLMError


def _ok_response() -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})


def _install_sequence(monkeypatch: pytest.MonkeyPatch, responses: list) -> dict:
    """Patch httpx.post to yield each item in order (an Exception is raised, a Response returned)."""
    state = {"calls": 0, "sleeps": []}

    def fake_post(*_a, **_k) -> httpx.Response:
        i = state["calls"]
        state["calls"] += 1
        item = responses[i]
        if isinstance(item, Exception):
            raise item
        return item

    def record_sleep(seconds: float) -> None:
        state["sleeps"].append(seconds)

    monkeypatch.setattr(anthropic_api.httpx, "post", fake_post)
    monkeypatch.setattr(anthropic_api, "_sleep", record_sleep)
    return state


def test_retries_network_error_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _install_sequence(monkeypatch, [httpx.ConnectError("boom"), _ok_response()])
    assert AnthropicApiAdapter(api_key="k").complete("hi") == "ok"
    assert state["calls"] == 2
    assert len(state["sleeps"]) == 1  # one backoff between attempts


def test_retries_retryable_status_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _install_sequence(monkeypatch, [httpx.Response(503, text="overloaded"), _ok_response()])
    assert AnthropicApiAdapter(api_key="k").complete("hi") == "ok"
    assert state["calls"] == 2


def test_does_not_retry_non_retryable_status(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _install_sequence(monkeypatch, [httpx.Response(401, text="bad key"), _ok_response()])
    with pytest.raises(AnyLLMError):
        AnthropicApiAdapter(api_key="k").complete("hi")
    assert state["calls"] == 1  # 401 is not retried


def test_raises_after_exhausting_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    seq = [httpx.Response(503, text="overloaded")] * anthropic_api._MAX_ATTEMPTS
    state = _install_sequence(monkeypatch, seq)
    with pytest.raises(AnyLLMError) as exc:
        AnthropicApiAdapter(api_key="k").complete("hi")
    assert state["calls"] == anthropic_api._MAX_ATTEMPTS
    assert exc.value.retryable is True


def test_honors_retry_after_header(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _install_sequence(
        monkeypatch,
        [httpx.Response(503, headers={"retry-after": "1.5"}, text="slow down"), _ok_response()],
    )
    assert AnthropicApiAdapter(api_key="k").complete("hi") == "ok"
    assert state["sleeps"] == [1.5]


def test_argv_has_json_format_and_model_no_bare() -> None:
    argv = build_argv("hello", "claude-sonnet-4-6")
    assert "--output-format" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    assert "--model" in argv
    assert "--bare" not in argv  # non-negotiable: never force API-key auth


def test_argv_without_model() -> None:
    argv = build_argv("hello", None)
    assert "--model" not in argv
    assert "--bare" not in argv


def test_child_env_scrubs_anthropic_api_key() -> None:
    env = child_env({"ANTHROPIC_API_KEY": "sk-secret", "PATH": "/usr/bin", "HOME": "/h"})
    assert "ANTHROPIC_API_KEY" not in env  # the #37686 footgun
    assert env["PATH"] == "/usr/bin"


def test_complete_fails_loud_on_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ClaudeCodeCliAdapter()
    monkeypatch.setattr(adapter, "available", lambda: True)

    def _fake_run(*_a, **_k):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="credit exhausted")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    with pytest.raises(AnyLLMError) as exc:
        adapter.complete("hi", model="m")
    assert "exited 1" in str(exc.value)


def test_complete_parses_json_result(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ClaudeCodeCliAdapter()
    monkeypatch.setattr(adapter, "available", lambda: True)

    def _fake_run(*_a, **_k):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout='{"result": "distilled summary"}', stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    assert adapter.complete("hi", model="m") == "distilled summary"


def test_complete_fails_on_non_json(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ClaudeCodeCliAdapter()
    monkeypatch.setattr(adapter, "available", lambda: True)
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess([], 0, "not json", ""))
    with pytest.raises(AnyLLMError):
        adapter.complete("hi")


def test_missing_cli_raises_before_running(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ClaudeCodeCliAdapter()
    monkeypatch.setattr(adapter, "available", lambda: False)
    with pytest.raises(AnyLLMError):
        adapter.complete("hi")
