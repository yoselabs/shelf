"""Which reasoning-effort levels a harness says a model accepts: local files only, None when it cannot tell."""

import json
from pathlib import Path

from any_agent.harnesses import ClaudeHarness, CodexHarness, OpenCodeHarness
from any_agent.testing import FakeEffortLevels

FIXTURE = Path(__file__).parent / "golden" / "codex_models_cache.json"


def codex(tmp_path: Path, body: str | None) -> CodexHarness:
    if body is not None:
        (tmp_path / "models_cache.json").write_text(body)
    return CodexHarness(env={"CODEX_HOME": str(tmp_path)})


def test_codex_reads_the_levels_of_each_model_from_its_models_cache(tmp_path):
    h = codex(tmp_path, FIXTURE.read_text())
    assert h.effort_levels("gpt-6.1-sol") == ("low", "medium", "high", "xhigh", "max", "ultra")
    assert h.effort_levels("gpt-6-luna") == ("low", "medium", "high", "xhigh", "max")


def test_codex_cannot_tell_for_an_unknown_model_a_missing_file_or_a_broken_one(tmp_path):
    assert codex(tmp_path, FIXTURE.read_text()).effort_levels("nope") is None
    assert codex(tmp_path, FIXTURE.read_text()).effort_levels("") is None
    assert CodexHarness(env={"CODEX_HOME": str(tmp_path / "absent")}).effort_levels("gpt-6.1-sol") is None
    assert codex(tmp_path, "{not json").effort_levels("gpt-6.1-sol") is None
    assert codex(tmp_path, json.dumps({"models": [{"slug": "m"}]})).effort_levels("m") is None


def test_claude_names_the_cli_levels_and_opencode_cannot_tell():
    assert ClaudeHarness(env={}).effort_levels("any") == ("low", "medium", "high", "xhigh", "max")
    assert OpenCodeHarness(env={}).effort_levels("any") is None


def test_the_fake_answers_per_model():
    fake = FakeEffortLevels({"m": ("low", "high"), "n": None})
    assert (fake.effort_levels("m"), fake.effort_levels("n"), fake.effort_levels("z")) == (("low", "high"), None, None)
