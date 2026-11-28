"""What the gate prints is bounded: a green gate in a line or two, a red one in the head of each failed log, not all of it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from any_gate.steps import FAILED_LOG_LINES, Report, Step, note, render

if TYPE_CHECKING:
    import pytest

STEPS = ("guard", "preset", "render", "blueprint", "secrets", "lint", "typecheck", "spell", "deps", "test", "scripts", "arch", "tag-check")


def _render(steps: tuple[Step, ...]) -> str:
    return "\n".join(render(Report(steps, 30), step_budget=60.0, gate_budget=180.0))


def test_a_green_gate_prints_under_a_kilobyte() -> None:
    out = _render(tuple(Step(name, 0, 2, "noisy log line\n" * 500) for name in STEPS))
    assert len(out) < 1000
    assert "noisy log line" not in out


def test_a_failed_step_prints_head_10_tail_10_and_where_the_log_is() -> None:
    log = "".join(f"src/m{n}.py:{n}: finding {n}\n" for n in range(5000))
    out = _render((Step("lint", 1, 2, log, log_path="/git/gate-logs/lint.log"), Step("test", 0, 3, "")))
    shown = out.splitlines()
    assert len(out) < 2000
    assert "src/m9.py" in out
    assert "src/m10.py" not in out
    assert "src/m4990.py" in out
    assert "src/m4989.py" not in out
    assert f"... {5000 - FAILED_LOG_LINES} more lines ..." in shown
    assert "log: /git/gate-logs/lint.log" in shown
    assert "FAIL lint 2s | log /git/gate-logs/lint.log" in shown


def test_a_short_failed_log_is_printed_whole_with_no_gap() -> None:
    out = _render((Step("lint", 1, 2, "one finding\ntwo findings\n"),))
    assert "one finding\ntwo findings" in out
    assert "more lines" not in out


def test_no_output_line_passes_200_characters() -> None:
    out = _render((Step("lint", 1, 2, "x" * 20000 + "\n"),))
    assert max(len(line) for line in out.splitlines()) <= 200


def test_every_step_has_one_line_with_its_reason_and_its_note() -> None:
    steps = (
        Step("test", 0, 24, "gate-note: 2/41 suites\n"),
        Step("lint", 0, 3, ""),
        Step("typecheck", 0, 0, "skipped typecheck: none of *.py changed\n"),
    )
    why = {"test": "run test: 3 changed (*.py)", "lint": "run lint: no gate passed this tree"}
    shown = render(Report(steps, 27), step_budget=60.0, gate_budget=180.0, why=why)
    assert "ok   test 24s | 3 changed (*.py) | 2/41 suites" in shown
    assert "ok   lint 3s | no gate passed this tree" in shown
    assert "skipped typecheck: none of *.py changed" in shown  # the prefix other tools scan for
    assert shown[-1] == "gate ok | 2 ok 1 skipped | 27s"


def test_a_step_that_did_zero_work_when_told_to_run_is_a_warning() -> None:
    steps = (Step("deps", 0, 1, "gate-note: 0 pkgs reached\n"),)
    shown = render(Report(steps, 1), step_budget=60.0, gate_budget=180.0, why={"deps": "run deps: changed files unknown"})
    assert shown[0] == "WARN deps 1s | changed files unknown | 0 pkgs reached"
    assert shown[-1] == "gate ok | 1 WARN | 1s"


def test_a_zero_note_on_a_step_nobody_told_to_run_is_not_a_warning() -> None:
    shown = render(Report((Step("deps", 0, 1, "gate-note: 0 pkgs reached\n"),), 1), step_budget=60.0, gate_budget=180.0)
    assert shown[0].startswith("ok   deps")


def test_note_writes_one_prefixed_line(capsys: pytest.CaptureFixture[str]) -> None:
    note("2/41 suites")
    assert capsys.readouterr().out == "gate-note: 2/41 suites\n"
