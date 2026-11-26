"""What the gate prints is bounded: a green gate in a line or two, a red one in the head of each failed log, not all of it."""

from __future__ import annotations

from any_gate.steps import FAILED_LOG_LINES, Report, Step, render

STEPS = ("guard", "preset", "render", "blueprint", "secrets", "lint", "typecheck", "spell", "deps", "test", "scripts", "arch", "tag-check")


def _render(steps: tuple[Step, ...]) -> str:
    return "\n".join(render(Report(steps, 30), step_budget=60.0, gate_budget=180.0))


def test_a_green_gate_prints_under_a_kilobyte() -> None:
    out = _render(tuple(Step(name, 0, 2, "noisy log line\n" * 500) for name in STEPS))
    assert len(out) < 1000
    assert "noisy log line" not in out


def test_a_failed_step_prints_the_head_of_its_log_and_says_how_to_get_the_rest() -> None:
    log = "".join(f"src/m{n}.py:{n}: finding {n}\n" for n in range(5000))
    out = _render((Step("lint", 1, 2, log), Step("test", 0, 3, "")))
    shown = out.splitlines()
    assert len(out) < 8000
    assert f"src/m{FAILED_LOG_LINES - 1}.py" in out
    assert f"src/m{FAILED_LOG_LINES}.py" not in out
    assert f"... {5000 - FAILED_LOG_LINES} more lines: `just lint` prints them all" in shown


def test_a_short_failed_log_is_printed_whole_with_no_pointer() -> None:
    out = _render((Step("lint", 1, 2, "one finding\ntwo findings\n"),))
    assert "one finding\ntwo findings" in out
    assert "more lines" not in out
