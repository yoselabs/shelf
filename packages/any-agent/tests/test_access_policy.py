"""The typed access policy: defaults equal the old launches; a choice reaches the argv; a wrong one is refused."""

from typing import Any

import pytest

from any_agent import ClaudeAccess, ClaudePermissionMode, CodexAccess, CodexApproval, CodexSandbox
from any_agent.harnesses.claude import ClaudeHarness, launch_argv
from any_agent.harnesses.codex import CodexHarness
from any_agent.protocol import LaunchInputs

INPUTS: dict[str, Any] = {
    "exe": "/bin/x",
    "cwd": "/w",
    "model": "m",
    "effort": "high",
    "prompt": "brief",
    "env": {},
    "session": "rid",
    "system": "r",
    "settings": '{"a": 1}',
}


def make(**kw: Any) -> LaunchInputs:
    return LaunchInputs(**(INPUTS | kw))


def after(argv: list[str], flag: str) -> str:
    return argv[argv.index(flag) + 1]


def test_claude_without_a_policy_keeps_auto_and_the_callers_settings():
    argv = launch_argv(make())
    assert after(argv, "--permission-mode") == "auto"
    assert after(argv, "--settings") == '{"a": 1}'
    assert launch_argv(make(access_policy=ClaudeAccess())) == argv


def test_claude_takes_the_chosen_mode_and_settings():
    policy = ClaudeAccess(permission_mode=ClaudePermissionMode.ACCEPT_EDITS, settings='{"b": 2}')
    argv = ClaudeHarness().launch_spec(make(access_policy=policy)).argv
    assert after(argv, "--permission-mode") == "acceptEdits"
    assert after(argv, "--settings") == '{"b": 2}'


def test_claude_refuses_what_is_not_in_the_vocabulary():
    with pytest.raises(ValueError, match="not a valid ClaudePermissionMode"):
        ClaudeAccess(permission_mode="bypassPermissions")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="not JSON"):
        ClaudeAccess(settings="{")
    with pytest.raises(ValueError, match="JSON object"):
        ClaudeAccess(settings="[]")


def test_a_harness_refuses_another_harnesss_policy():
    with pytest.raises(ValueError, match="claude cannot take a CodexAccess"):
        launch_argv(make(access_policy=CodexAccess()))
    with pytest.raises(ValueError, match="codex cannot take a ClaudeAccess"):
        CodexHarness().launch_spec(make(access_policy=ClaudeAccess()))


def test_codex_without_a_policy_is_unchanged():
    spec = CodexHarness().launch_spec(make(sandbox="workspace-write", access=["-c", "x=1"]))
    head = ["/bin/x", "exec", "-m", "m", "-c", 'model_reasoning_effort="high"']
    assert spec.argv == [*head, "-s", "workspace-write", "-c", "x=1", "--json", "-"]


def test_codex_policy_translates_sandbox_approval_network_and_roots():
    policy = CodexAccess(sandbox=CodexSandbox.WORKSPACE_WRITE, approval=CodexApproval.NEVER, network=False, writable_roots=("/t",))
    argv = CodexHarness().launch_spec(make(access_policy=policy)).argv
    assert after(argv, "-s") == "workspace-write"
    assert 'approval_policy="never"' in argv
    assert "sandbox_workspace_write.network_access=false" in argv
    assert 'sandbox_workspace_write.writable_roots=["/t"]' in argv
    resumed = CodexHarness().launch_spec(make(access_policy=policy, resume="r1")).argv
    assert 'sandbox_mode="workspace-write"' in resumed
    assert "-s" not in resumed


def test_codex_refuses_choices_its_sandbox_cannot_honour():
    with pytest.raises(ValueError, match="workspace-write sandbox only"):
        CodexAccess(sandbox=CodexSandbox.READ_ONLY, network=True)
    with pytest.raises(ValueError, match="must be absolute"):
        CodexAccess(writable_roots=("rel",))
    with pytest.raises(ValueError, match="not a valid CodexSandbox"):
        CodexAccess(sandbox="yolo")  # type: ignore[arg-type]
