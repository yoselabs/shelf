"""A sealed launch is a pure completion: only the caller's system and user text reach the model, whatever the host has configured.

Asserted on the final LaunchSpec each harness returns, with a hostile fictional HOME and project that carry a hook which must never run.
No child process, no model.
"""

from pathlib import Path
from typing import Any

import pytest

from any_agent import ClaudeHarness, CodexHarness, LaunchInputs, OpenCodeHarness

SEALED_CLAUDE = (
    "-p",
    "--output-format",
    "json",
    "--safe-mode",
    "--tools",
    "--strict-mcp-config",
    "--disable-slash-commands",
    "--no-session-persistence",
    "--max-turns",
    "--system-prompt",
)
SEALED_CODEX = ("exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules", "--ephemeral")


def hostile(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A fictional HOME and project whose hook, CLAUDE.md and MCP config would each leave a mark if anything loaded them."""
    mark = tmp_path / "hook-ran"
    home, project = tmp_path / "home", tmp_path / "project"
    (home / ".claude").mkdir(parents=True)
    (project / ".claude").mkdir(parents=True)
    hook = {"hooks": {"SessionEnd": [{"hooks": [{"type": "command", "command": f"touch {mark}"}]}]}}
    (home / ".claude" / "settings.json").write_text(str(hook), encoding="utf-8")
    (project / "CLAUDE.md").write_text("ambient rules", encoding="utf-8")
    (project / ".mcp.json").write_text("{}", encoding="utf-8")
    (project / "AGENTS.md").write_text("ambient rules", encoding="utf-8")
    return home, project, mark


def claude_inputs(project: Path, **kw: Any) -> LaunchInputs:
    base: dict[str, Any] = {
        "exe": "/bin/claude",
        "cwd": str(project),
        "model": "",
        "effort": "low",
        "prompt": "question",
        "env": {"ANTHROPIC_API_KEY": "must-not-bill", "PATH": "/bin"},
        "system": "rules",
        "sealed": True,
    }
    return LaunchInputs(**(base | kw))


def test_claude_sealed_argv_names_every_closed_door(tmp_path):
    _, project, _ = hostile(tmp_path)
    harness = ClaudeHarness()
    try:
        spec = harness.launch_spec(claude_inputs(project, model="chosen"))
        argv = spec.argv
        assert all(flag in argv for flag in SEALED_CLAUDE)
        assert argv[argv.index("--tools") + 1] == ""
        assert argv[argv.index("--setting-sources") + 1] == ""
        assert argv[argv.index("--max-turns") + 1] == "1"
        assert argv[argv.index("--system-prompt") + 1] == "rules"
        assert argv[argv.index("--model") + 1] == "chosen"
        assert not {"--append-system-prompt", "--bare", "--restricted", "--resume", "--session-id", "--settings"} & set(argv)
        assert spec.stdin == "question"
    finally:
        harness.cleanup()


def test_claude_sealed_replaces_an_empty_system_too(tmp_path):
    """No system text still replaces the default coding prompt; it never falls back to it."""
    _, project, _ = hostile(tmp_path)
    harness = ClaudeHarness()
    try:
        argv = harness.launch_spec(claude_inputs(project, system="")).argv
        assert argv[argv.index("--system-prompt") + 1] == ""
        assert "--model" not in argv
    finally:
        harness.cleanup()


def test_claude_sealed_runs_in_an_empty_directory_that_cleanup_removes(tmp_path):
    _, project, _ = hostile(tmp_path)
    harness = ClaudeHarness()
    spec = harness.launch_spec(claude_inputs(project))
    sealed_cwd = Path(spec.cwd)
    assert sealed_cwd != project
    assert sealed_cwd.is_dir()
    assert list(sealed_cwd.iterdir()) == []  # no CLAUDE.md, .mcp.json or .claude to discover
    harness.cleanup()
    assert not sealed_cwd.exists()


def test_claude_sealed_keeps_the_subscription_login(tmp_path):
    _, project, _ = hostile(tmp_path)
    harness = ClaudeHarness()
    try:
        spec = harness.launch_spec(claude_inputs(project))
        assert "ANTHROPIC_API_KEY" not in spec.env
        assert spec.env["PATH"] == "/bin"
        assert "--bare" not in spec.argv
    finally:
        harness.cleanup()


def test_claude_unsealed_launch_is_unchanged(tmp_path):
    _, project, _ = hostile(tmp_path)
    inputs = claude_inputs(project, sealed=False, session="rid", settings="{}")
    spec = ClaudeHarness().launch_spec(inputs)
    assert spec.cwd == str(project)
    assert "--safe-mode" not in spec.argv
    assert "--append-system-prompt" in spec.argv


def codex_inputs(project: Path, **kw: Any) -> LaunchInputs:
    base: dict[str, Any] = {
        "exe": "/bin/codex",
        "cwd": str(project),
        "model": "",
        "effort": "low",
        "prompt": "rules\n\nquestion",
        "env": {"PATH": "/bin"},
        "sealed": True,
    }
    return LaunchInputs(**(base | kw))


def test_codex_sealed_argv_ignores_user_config_and_rules(tmp_path):
    _, project, _ = hostile(tmp_path)
    harness = CodexHarness()
    try:
        spec = harness.launch_spec(codex_inputs(project, model="chosen"))
        argv = spec.argv
        assert all(flag in argv for flag in SEALED_CODEX)
        assert argv[argv.index("--model") + 1] == "chosen"
        assert argv[-1] == "-"
        assert spec.stdin == "rules\n\nquestion"
        assert Path(argv[argv.index("-o") + 1]).parent.is_dir()
    finally:
        harness.cleanup()


def test_codex_sealed_runs_in_an_empty_directory_that_cleanup_removes(tmp_path):
    """AGENTS.md of the project is never discovered, and the answer file is cleaned up with the directory."""
    _, project, _ = hostile(tmp_path)
    harness = CodexHarness()
    spec = harness.launch_spec(codex_inputs(project))
    sealed_cwd = Path(spec.cwd)
    assert sealed_cwd != project
    assert not (sealed_cwd / "AGENTS.md").exists()
    out = Path(spec.argv[spec.argv.index("-o") + 1])
    assert out.parent.is_dir()
    harness.cleanup()
    assert not sealed_cwd.exists()
    assert not out.parent.exists()


def test_codex_unsealed_launch_is_unchanged(tmp_path):
    _, project, _ = hostile(tmp_path)
    inputs = codex_inputs(project, sealed=False, cli=["/bin/codex", "exec", "-s", "read-only"], out_file="/o")
    spec = CodexHarness().launch_spec(inputs)
    assert spec.cwd == str(project)
    assert "--ignore-user-config" not in spec.argv


@pytest.mark.parametrize("harness_type", [ClaudeHarness, CodexHarness])
def test_cleanup_is_safe_without_a_sealed_launch(harness_type):
    harness_type().cleanup()


def test_a_harness_without_a_sealed_launch_refuses_instead_of_ignoring_it(tmp_path):
    """A pure completion the harness cannot guarantee is an error, never a silently unsealed run."""
    inputs = LaunchInputs(exe="/bin/opencode", cwd=str(tmp_path), model="m", effort="low", prompt="p", env={}, sealed=True)
    with pytest.raises(ValueError, match="no sealed launch"):
        OpenCodeHarness().launch_spec(inputs)
