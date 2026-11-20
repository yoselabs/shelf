"""The CLI's three verbs: init, check, and the gate steps (docs/missions/blueprint-cli/verb-review.md)."""

from __future__ import annotations

import pytest
from blueprint.__main__ import main


def _help(capsys: pytest.CaptureFixture[str], *argv: str) -> str:
    with pytest.raises(SystemExit) as stop:
        main([*argv, "--help"])
    assert stop.value.code == 0
    return capsys.readouterr().out


def test_the_top_level_help_names_three_verbs_and_calls_gate_the_steps_of_just_check(capsys: pytest.CaptureFixture[str]) -> None:
    out = _help(capsys)
    for word in ("init", "check", "gate", "steps of `just check`"):
        assert word in out
    for gone in ("survey", "template", "recipe", "checkpoints"):
        assert gone not in out


def test_the_gate_help_says_what_each_step_does_and_that_the_justfile_runs_them(capsys: pytest.CaptureFixture[str]) -> None:
    out = _help(capsys, "gate")
    assert "justfile" in out
    for step in ("guard", "preset", "render", "test", "adr-index"):
        assert step in out


@pytest.mark.parametrize("old", ["guard", "preset", "render", "test", "adr-index", "checkpoints", "survey", "template", "recipe"])
def test_the_old_top_level_verbs_are_gone(old: str) -> None:
    with pytest.raises(SystemExit) as stop:
        main([old])
    assert stop.value.code == 2


def test_check_has_no_summary_or_gate_flag_but_a_brief_one() -> None:
    for flag in ("--summary", "--gate"):
        with pytest.raises(SystemExit) as stop:
            main(["check", flag])
        assert stop.value.code == 2


def test_init_answers_help_and_names_no_hooks(capsys: pytest.CaptureFixture[str]) -> None:
    assert "--no-hooks" in _help(capsys, "init")
