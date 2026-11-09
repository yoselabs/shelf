"""CLI completion scenarios at the harness/run boundary; no child processes or network."""

import asyncio
import importlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from anyllm import ProviderName, build_adapter
from anyllm.errors import AnyLLMError
from anyllm.select import DEFAULT_ORDER, DEFAULT_PROVIDER


@pytest.fixture(params=[("claude_code_cli", "ClaudeCodeCliAdapter", "claude"), ("codex_cli", "CodexCliAdapter", "codex")])
def backend(request, monkeypatch):
    module, adapter, binary = request.param
    provider = importlib.import_module(f"anyllm.providers.{module}")

    async def to_thread(function, *args):
        return function(*args)

    # Keep the supervisor boundary fake, including its executor dispatch.
    monkeypatch.setattr("anyllm.providers._agent.asyncio.to_thread", to_thread)
    monkeypatch.setattr(provider.shutil, "which", lambda _: f"/bin/{binary}")
    return provider, getattr(provider, adapter)(), binary


def test_success_and_launch_safeguards(backend, monkeypatch):
    provider, adapter, binary = backend
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-bill")
    specs = []

    def run(harness, spec, timeout):
        specs.append(spec)
        assert spec.stdin == "question" if binary == "claude" else "rules\n\nquestion" in spec.stdin
        if binary == "claude":
            harness.parse_line(
                json.dumps(
                    {"type": "result", "result": "answer", "total_cost_usd": 0.02, "usage": {"input_tokens": 12, "output_tokens": 5}}
                )
            )
        else:
            harness.parse_line(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "answer"}}))
            harness.parse_line(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 5}}))
        return provider.any_agent.RunOutcome(rc=0, summary=harness.summary(0, "", "", None, False))

    monkeypatch.setattr(provider.any_agent, "run", run)
    result = asyncio.run(adapter.complete(user="question", system="rules", model="chosen"))
    assert (result.text, result.model, result.prompt_tokens, result.completion_tokens, result.cost_usd) == (
        "answer",
        "chosen",
        12,
        5,
        0.02 if binary == "claude" else 0.0,
    )
    assert result.latency_ms >= 0
    spec = specs[0]
    assert "ANTHROPIC_API_KEY" not in spec.env
    assert "--bare" not in spec.argv
    if binary == "claude":
        assert spec.argv[spec.argv.index("--output-format") + 1] == "json"
        assert "stream-json" not in spec.argv
        assert spec.argv[spec.argv.index("--system-prompt") + 1] == "rules"
        assert "--append-system-prompt" not in spec.argv
    else:
        assert "exec" in spec.argv and "--json" in spec.argv
    assert spec.cwd != str(Path.cwd())  # an empty directory: no project instruction file is discovered


def test_pure_completion_closes_the_same_doors_on_every_cli(backend, monkeypatch):
    """The final LaunchSpec of each CLI provider names what it shuts: user config, rules, tools, hooks, session file."""
    provider, adapter, binary = backend
    seen: dict[str, Any] = {}

    def run(harness, spec, timeout):
        seen["argv"], seen["cwd"] = spec.argv, spec.cwd
        seen["empty"] = list(Path(spec.cwd).iterdir()) == []
        return provider.any_agent.RunOutcome(rc=0, summary=harness.summary(0, "", "", None, False))

    monkeypatch.setattr(provider.any_agent, "run", run)
    with pytest.raises(AnyLLMError):
        asyncio.run(adapter.complete(user="question", system=""))
    argv = seen["argv"]
    shut = {
        "claude": ["--safe-mode", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"],
        "codex": ["--ignore-user-config", "--ignore-rules", "--ephemeral"],
    }[binary]
    assert all(flag in argv for flag in shut)
    assert seen["empty"] is True
    assert not Path(str(seen["cwd"])).exists()  # removed once the call ends, failed or not
    if binary == "claude":
        assert argv[argv.index("--system-prompt") + 1] == ""  # empty system still replaces the default prompt
        assert argv[argv.index("--max-turns") + 1] == "1"


@pytest.mark.parametrize(("rc", "vendor"), [(1, "broken"), (0, "Not logged in"), (0, "Credit balance is too low")])
def test_failures_never_fall_back_to_api(backend, monkeypatch, rc, vendor):
    provider, adapter, binary = backend
    run = Mock(
        return_value=SimpleNamespace(
            rc=rc,
            timed_out=False,
            stop=None,
            summary=SimpleNamespace(text="", rc=rc, vendor=vendor, stderr=vendor, work=False, facts={}, res={}, cost=0),
        )
    )
    monkeypatch.setattr(provider.any_agent, "run", run)
    with pytest.raises(AnyLLMError) as caught:
        asyncio.run(adapter.complete(user="hello"))
    assert not caught.value.retryable
    assert caught.value.hint is not None
    assert "never falls back" in caught.value.hint
    assert binary in str(caught.value)
    run.assert_called_once()


def test_missing_binary(backend, monkeypatch):
    provider, adapter, _ = backend
    monkeypatch.setattr(provider.shutil, "which", lambda _: None)
    assert not adapter.available()
    with pytest.raises(AnyLLMError, match="not found on PATH"):
        asyncio.run(adapter.complete(user="hello"))


def test_missing_extra(backend, monkeypatch):
    provider, adapter, _ = backend
    monkeypatch.setattr(provider, "any_agent", None)
    assert not adapter.available()
    with pytest.raises(AnyLLMError) as caught:
        asyncio.run(adapter.complete(user="hello"))
    assert not caught.value.retryable
    assert caught.value.hint == "install anyllm[agent]"


def test_codex_selection(backend):
    _, adapter, binary = backend
    assert build_adapter(adapter.name).name == adapter.name
    assert DEFAULT_PROVIDER == ProviderName.CLAUDE_CODE_CLI
    assert DEFAULT_ORDER[:2] == (ProviderName.CLAUDE_CODE_CLI, ProviderName.CODEX_CLI)
    assert binary in {"claude", "codex"}


def test_base_import_without_agent():
    """A clean interpreter's module graph can import both entry points without the extra."""
    code = """
import sys
sys.modules['any_agent'] = None
sys.modules['stream_proc'] = None
import anyllm
import anyllm.select
assert not anyllm.ClaudeCodeCliAdapter().available()
assert not anyllm.CodexCliAdapter().available()
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True)
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())["project"]
    assert project["dependencies"] == []
    assert project["optional-dependencies"]["agent"] == ["any-agent>=0.1.3,<1"]


def test_invalid_output_fails_loud(backend, monkeypatch):
    provider, adapter, _ = backend

    def run(harness, spec, timeout):
        return provider.any_agent.RunOutcome(rc=0, summary=harness.summary(0, "not json", "", None, False))

    monkeypatch.setattr(provider.any_agent, "run", run)
    with pytest.raises(AnyLLMError):
        asyncio.run(adapter.complete(user="hello"))
