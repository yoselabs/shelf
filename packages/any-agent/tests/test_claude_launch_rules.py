"""Claude's launch rules, in one place: never --bare, never an API key in the child's environment."""

from typing import Any

import pytest

from any_agent import claude
from any_agent.claude import ClaudeHarness, launch_argv, launch_env
from any_agent.harness import LaunchInputs

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


def test_a_launch_never_passes_bare():
    kws: list[dict[str, Any]] = [{}, {"write": True}, {"resume": "old"}]
    for kw in kws:
        assert "--bare" not in launch_argv(make(**kw))


def test_the_rule_is_enforced_not_just_followed(monkeypatch):
    monkeypatch.setattr(claude, "FORBIDDEN_FLAGS", ("--bare", "-p"))  # a flag the argv does carry
    with pytest.raises(ValueError, match="never launched with -p"):
        launch_argv(make())
