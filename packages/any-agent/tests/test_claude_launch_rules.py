"""Claude's launch rules, in one place: never --bare, never an API key in the child's environment."""

from typing import Any

import pytest

from any_agent.harnesses import claude
from any_agent.harnesses.claude import ClaudeHarness, launch_argv, launch_env
from any_agent.protocol import LaunchInputs

INPUTS: dict[str, Any] = {
    "exe": "/bin/claude",
    "cwd": "/w",
    "model": "m",
    "effort": "high",
    "prompt": "brief",
    "env": {},
    "session": "rid",
    "system": "r",
    "settings": "{}",
}


def make(**kw: Any) -> LaunchInputs:
    return LaunchInputs(**(INPUTS | kw))


def test_the_api_key_never_reaches_the_child():
    env = {"ANTHROPIC_API_KEY": "sk-x", "PATH": "/bin", "HOME": "/h"}
    spec = ClaudeHarness().launch_spec(make(env=env))
    assert spec.env == {"PATH": "/bin", "HOME": "/h"}
    assert env["ANTHROPIC_API_KEY"] == "sk-x"  # the caller's dict is not touched
    assert launch_env({"ANTHROPIC_API_KEY": "k"}) == {}


def test_an_api_key_lane_keeps_its_key_and_needs_one():
    env = {"ANTHROPIC_API_KEY": "sk-x", "PATH": "/bin"}
    assert ClaudeHarness().launch_spec(make(env=env, auth="api_key")).env == env
    with pytest.raises(ValueError, match="needs ANTHROPIC_API_KEY"):
        launch_env({"PATH": "/bin"}, "api_key")
    with pytest.raises(ValueError, match="one of subscription, api_key"):
        launch_env({}, "both")


def test_a_launch_never_passes_bare():
    kws: list[dict[str, Any]] = [{}, {"write": True}, {"resume": "old"}]
    for kw in kws:
        assert "--bare" not in launch_argv(make(**kw))


def test_the_rule_is_enforced_not_just_followed(monkeypatch):
    monkeypatch.setattr(claude, "FORBIDDEN_FLAGS", ("--bare", "-p"))  # a flag the argv does carry
    with pytest.raises(ValueError, match="never launched with -p"):
        launch_argv(make())


def test_an_ambient_bare_marker_never_reaches_a_subscription_child():
    """CLAUDE_CODE_SIMPLE=1 is what --bare sets: claude then reads an API key only and never the login."""
    env = {"CLAUDE_CODE_SIMPLE": "1", "PATH": "/bin"}
    assert launch_env(env) == {"PATH": "/bin"}
    assert ClaudeHarness().launch_spec(make(env=env)).env == {"PATH": "/bin"}
    sealed = ClaudeHarness()
    try:
        assert "CLAUDE_CODE_SIMPLE" not in sealed.launch_spec(make(env=env, sealed=True)).env
    finally:
        sealed.cleanup()


@pytest.mark.parametrize("name", ["ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"])
def test_a_variable_that_moves_the_lane_is_refused_not_ignored(name):
    with pytest.raises(ValueError, match=name):
        launch_env({name: "1", "PATH": "/bin"})
    harness = ClaudeHarness()
    try:
        with pytest.raises(ValueError, match=name):
            harness.launch_spec(make(env={name: "1"}, sealed=True))
    finally:
        harness.cleanup()


@pytest.mark.parametrize("value", ["", "0", "false", "False"])
def test_a_lane_variable_set_off_is_not_refused(value):
    assert launch_env({"CLAUDE_CODE_USE_BEDROCK": value, "PATH": "/bin"})["PATH"] == "/bin"


def test_the_api_key_lane_keeps_every_variable_it_was_given():
    env = {"ANTHROPIC_API_KEY": "k", "CLAUDE_CODE_SIMPLE": "1", "CLAUDE_CODE_USE_BEDROCK": "1"}
    assert launch_env(env, "api_key") == env
