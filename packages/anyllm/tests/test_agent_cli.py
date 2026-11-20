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


def _env(tmp_path: Path, binary: str, **more: str) -> dict[str, str]:
    """An injected environment whose PATH holds one executable `binary`: the only place discovery may look."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    exe = bin_dir / binary
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    return {"PATH": str(bin_dir), "HOME": str(tmp_path / "home"), **more}


@pytest.fixture(params=[("claude_code_cli", "ClaudeCodeCliAdapter", "claude"), ("codex_cli", "CodexCliAdapter", "codex")])
def backend(request, monkeypatch, tmp_path):
    module, adapter, binary = request.param
    provider = importlib.import_module(f"anyllm.providers.{module}")

    async def to_thread(function, *args):
        return function(*args)

    # Keep the supervisor boundary fake, including its executor dispatch.
    monkeypatch.setattr("anyllm.providers._agent.asyncio.to_thread", to_thread)
    return provider, getattr(provider, adapter)(env=_env(tmp_path, binary)), binary


def test_success_and_launch_safeguards(backend, monkeypatch):
    provider, _, binary = backend
    adapter = type(backend[1])(
        env={
            **backend[1]._env,
            "ANTHROPIC_API_KEY": "must-not-bill",
            "OPENAI_API_KEY": "must-not-bill",
            "CLAUDE_CODE_SIMPLE": "1",  # what --bare sets: it would hide the subscription login from claude
        }
    )
    specs = []

    def run(harness, spec, timeout, hooks=None):
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
    if binary == "claude":
        assert "CLAUDE_CODE_SIMPLE" not in spec.env
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

    def run(harness, spec, timeout, hooks=None):
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


def test_missing_binary(backend, tmp_path):
    _, adapter, _ = backend
    adapter = type(adapter)(env={"PATH": str(tmp_path / "empty"), "HOME": str(tmp_path)})
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
    assert build_adapter(adapter.name, env=adapter._env).name == adapter.name
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
assert not anyllm.ClaudeCodeCliAdapter(env={"PATH": ""}).available()
assert not anyllm.CodexCliAdapter(env={"PATH": ""}).available()
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True)
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())["project"]
    assert project["dependencies"] == ["child-env>=0.2,<1"]
    assert project["optional-dependencies"]["agent"] == ["any-agent>=0.17.0,<1"]


def test_invalid_output_fails_loud(backend, monkeypatch):
    provider, adapter, _ = backend

    def run(harness, spec, timeout, hooks=None):
        return provider.any_agent.RunOutcome(rc=0, summary=harness.summary(0, "not json", "", None, False))

    monkeypatch.setattr(provider.any_agent, "run", run)
    with pytest.raises(AnyLLMError):
        asyncio.run(adapter.complete(user="hello"))


def test_an_environment_that_moves_the_lane_fails_loud_before_launch(monkeypatch, tmp_path):
    provider = importlib.import_module("anyllm.providers.claude_code_cli")
    run = Mock()
    monkeypatch.setattr(provider.any_agent, "run", run)
    adapter = provider.ClaudeCodeCliAdapter(env=_env(tmp_path, "claude", CLAUDE_CODE_USE_BEDROCK="1"))
    with pytest.raises(AnyLLMError, match="CLAUDE_CODE_USE_BEDROCK") as caught:
        asyncio.run(adapter.complete(user="hello"))
    assert not caught.value.retryable
    run.assert_not_called()


def _launched_env(provider, monkeypatch, adapter) -> dict[str, str]:
    seen: dict[str, dict[str, str]] = {}

    def run(harness, spec, timeout, hooks=None):
        seen["env"] = spec.env
        return provider.any_agent.RunOutcome(rc=0, summary=harness.summary(0, "", "", None, False))

    monkeypatch.setattr(provider.any_agent, "run", run)
    with pytest.raises(AnyLLMError):
        asyncio.run(adapter.complete(user="hello"))
    return seen["env"]


_AMBIENT = {
    "AWS_SECRET_ACCESS_KEY": "s",
    "GITHUB_TOKEN": "s",
    "SSH_AUTH_SOCK": "/s",
    "SOME_APP_SETTING": "x",
    "ANTHROPIC_API_KEY": "s",
    "OPENAI_API_KEY": "s",
}


def test_claude_child_gets_an_allow_list_not_the_whole_environment(monkeypatch, tmp_path):
    """Exactly: the user's place, proxy and CA settings, the config folder and the OAuth token (a container login); nothing else."""
    provider = importlib.import_module("anyllm.providers.claude_code_cli")
    kept = {"HTTPS_PROXY": "p", "NODE_EXTRA_CA_CERTS": "/ca", "CLAUDE_CONFIG_DIR": "/c", "CLAUDE_CODE_OAUTH_TOKEN": "tok", "LANG": "C"}
    env = _launched_env(provider, monkeypatch, provider.ClaudeCodeCliAdapter(env={**_env(tmp_path, "claude"), **kept, **_AMBIENT}))
    assert {k: env[k] for k in kept} == kept
    assert "HOME" in env
    assert not set(_AMBIENT) & set(env)


def test_codex_child_gets_an_allow_list_not_the_whole_environment(monkeypatch, tmp_path):
    provider = importlib.import_module("anyllm.providers.codex_cli")
    kept = {"HTTPS_PROXY": "p", "CODEX_HOME": "/codex", "LANG": "C"}
    env = _launched_env(provider, monkeypatch, provider.CodexCliAdapter(env={**_env(tmp_path, "codex"), **kept, **_AMBIENT}))
    assert {k: env[k] for k in kept} == kept
    assert "HOME" in env
    assert not set(_AMBIENT) & set(env)


def test_discovery_never_consults_the_process_path(backend, monkeypatch, tmp_path):
    """The injected PATH is the only one searched: a binary on the real PATH but not the injected one is not found."""
    _, adapter, binary = backend
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / binary).write_text("#!/bin/sh\n")
    (elsewhere / binary).chmod(0o755)
    monkeypatch.setenv("PATH", str(elsewhere))
    blind = type(adapter)(env={"PATH": str(tmp_path / "nothing"), "HOME": str(tmp_path)})
    assert not blind.available()
