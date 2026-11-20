"""`python -m any_gate steps`: the gate's steps at once, each into its own log, then one timing line and the log of every failure."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

# A stand-in for `just`: `fake NAME` behaves as the step NAME says.
FAKE = textwrap.dedent(
    """\
    #!/bin/sh
    case "$1" in
      ok) echo "ok output" ;;
      one) touch "$MEET/a"; n=0; while [ ! -e "$MEET/b" ] && [ $n -lt 100 ]; do sleep 0.1; n=$((n+1)); done; [ -e "$MEET/b" ] && echo one ;;
      two) touch "$MEET/b"; n=0; while [ ! -e "$MEET/a" ] && [ $n -lt 100 ]; do sleep 0.1; n=$((n+1)); done; [ -e "$MEET/a" ] && echo two ;;
      slow) sleep 2; echo slow output ;;
      fail) echo "boom: the reason"; exit 3 ;;
      skip) echo "skipped lint: no file changed" ;;
      wait) [ -n "$GATE_NOTICE_FD" ] && echo "gate-lock: waiting for a slot" >&"$GATE_NOTICE_FD"; echo "quiet log line" ;;
      env) echo "fd=$GATE_NOTICE_FD" ;;
    esac
    """
)


@pytest.fixture
def fake(tmp_path: Path) -> str:
    path = tmp_path / "fake-just"
    path.write_text(FAKE)
    path.chmod(0o755)
    return str(path)


def _steps(fake: str, *names: str, **env: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "any_gate", "steps", "--runner", fake, *names]
    return subprocess.run(cmd, capture_output=True, text=True, check=False, env={**os.environ, **env})


def test_every_step_passing_makes_a_pass_and_one_timing_line(fake: str) -> None:
    done = _steps(fake, "ok", "skip")
    assert done.returncode == 0
    assert "gate: ok skip (in parallel)" in done.stderr
    assert re.search(r"gate: ok \d+s · skip \d+s -- total \d+s", done.stderr)


def test_the_steps_run_at_once(fake: str, tmp_path: Path) -> None:
    # Each step waits for the other's marker (up to 10 s), so they pass only if both run at the same time. A wall-clock bound
    # failed on a loaded machine (2.0 s against a 1.8 s limit, 2026-11-20) while the steps were in fact parallel.
    done = _steps(fake, "one", "two", MEET=str(tmp_path))
    assert done.returncode == 0


def test_a_failing_step_fails_the_gate_and_prints_its_log_and_marks_it(fake: str) -> None:
    done = _steps(fake, "ok", "fail")
    assert done.returncode == 1
    assert "--- fail\nboom: the reason" in done.stderr
    assert re.search(r"fail \d+s ✗", done.stderr)
    assert "gate: failed: fail" in done.stderr
    assert "ok output" not in done.stderr  # a passing step's output stays in its log


def test_a_step_over_its_budget_is_marked_and_a_slow_gate_is_warned_about(fake: str) -> None:
    done = _steps(fake, "slow", "ok", GATE_STEP_BUDGET="1", GATE_BUDGET="1")
    assert done.returncode == 0
    assert re.search(r"slow \d+s ⚠ over 1s", done.stderr)
    assert "ok 0s ⚠" not in done.stderr
    assert re.search(r"gate: ⚠ \d+s is over the 1s gate budget", done.stderr)


def test_the_budgets_default_to_60_and_180_seconds(fake: str) -> None:
    done = _steps(fake, "ok")
    assert "⚠" not in done.stderr


def test_a_skipped_line_is_repeated_on_the_terminal(fake: str) -> None:
    done = _steps(fake, "skip", "ok")
    assert "skipped lint: no file changed" in done.stderr


def test_a_notice_reaches_the_terminal_and_stays_out_of_the_log(fake: str) -> None:
    done = _steps(fake, "wait", "fail")
    assert "gate-lock: waiting for a slot" in done.stderr
    assert "quiet log line" not in done.stderr  # only failed steps print their log, and `wait` passed


def test_a_step_is_told_where_the_terminal_is(fake: str) -> None:
    # the descriptor number is the caller's business; what a step needs is that the variable names an open one
    done = _steps(fake, "wait")
    assert done.returncode == 0
    assert "waiting for a slot" in done.stderr


def test_the_runner_defaults_to_just_and_a_missing_one_is_an_error() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "any_gate", "steps", "--runner", "/nonexistent/just", "ok"], capture_output=True, text=True, check=False
    )
    assert done.returncode == 1
    assert "failed: ok" in done.stderr


def test_no_step_names_is_a_usage_error(fake: str) -> None:
    done = _steps(fake)
    assert done.returncode == 2
