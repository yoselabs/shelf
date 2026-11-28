"""`python -m any_gate steps`: the gate's steps at once, each into its own log, then one timing line and the log of every failure."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import textwrap
import threading
from typing import TYPE_CHECKING

import pytest
from any_gate.steps import INTERNAL, _run_threads, run_steps

if TYPE_CHECKING:
    from pathlib import Path

# A stand-in for `just`: `fake NAME` behaves as the step NAME says.
FAKE = textwrap.dedent(
    """\
    #!/bin/sh
    case "$1" in
      ok) echo "ok output" ;;
      one) touch "$MEET/a"; n=0; while [ ! -e "$MEET/b" ] && [ $n -lt 300 ]; do sleep 0.1; n=$((n+1)); done; [ -e "$MEET/b" ] && echo one ;;
      two) touch "$MEET/b"; n=0; while [ ! -e "$MEET/a" ] && [ $n -lt 300 ]; do sleep 0.1; n=$((n+1)); done; [ -e "$MEET/a" ] && echo two ;;
      slow) sleep 2; echo slow output ;;
      hang) sleep 60 ;;
      pidhang) echo $$ > "$MEET/pid"; sleep 60 ;;
      x125) echo "docker said no"; exit 125 ;;
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


def _steps(fake: str, *names: str, flags: tuple[str, ...] = (), **env: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "any_gate", "steps", "--runner", fake, *flags, *names]
    return subprocess.run(cmd, capture_output=True, text=True, check=False, env={**os.environ, **env})


def test_every_step_passing_makes_a_pass_and_one_timing_line(fake: str) -> None:
    done = _steps(fake, "ok", "skip")
    assert done.returncode == 0
    assert re.search(r"^gate base=\S+ files=\S+: ok skip$", done.stderr, re.MULTILINE)
    assert re.search(r"^ok   ok \d+s \| declares no inputs$", done.stderr, re.MULTILINE)
    assert re.search(r"^gate ok \| 1 ok 1 skipped \| \d+s$", done.stderr, re.MULTILINE)


def test_the_steps_run_at_once(fake: str, tmp_path: Path) -> None:
    # Each step waits for the other's marker (up to 10 s), so they pass only if both run at the same time. A wall-clock bound
    # failed on a loaded machine (2.0 s against a 1.8 s limit, 2026-11-20) while the steps were in fact parallel.
    done = _steps(fake, "one", "two", MEET=str(tmp_path))
    assert done.returncode == 0


def test_a_failing_step_fails_the_gate_and_prints_its_log_and_marks_it(fake: str) -> None:
    done = _steps(fake, "ok", "fail")
    assert done.returncode == 1
    assert re.search(r"--- fail ✗ \d+s\nboom: the reason\nlog: \S+gate-logs/fail\.log", done.stderr)
    assert re.search(r"^FAIL fail \d+s", done.stderr, re.MULTILINE)
    assert "gate FAIL fail |" in done.stderr
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
    assert "gate FAIL ok" in done.stderr


def test_no_step_names_is_a_usage_error(fake: str) -> None:
    done = _steps(fake)
    assert done.returncode == 2


def test_a_failure_is_shown_while_the_other_steps_are_still_running(fake: str) -> None:
    cmd = [sys.executable, "-m", "any_gate", "steps", "--runner", fake, "slow", "fail"]
    with subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True) as proc:
        assert proc.stderr is not None
        seen = []
        for line in proc.stderr:
            seen.append(line)
            if line.startswith("--- fail"):
                assert proc.poll() is None  # `slow` has two seconds left: the failure did not wait for it
                break
        rest = proc.stderr.read()
        assert proc.wait() == 1
    assert "boom: the reason" in rest
    assert "gate FAIL fail" in rest


def test_a_step_over_its_limit_has_its_whole_tree_stopped_and_is_named(fake: str) -> None:
    done = _steps(fake, "hang", "ok", flags=("--step-limit", "1"))
    assert done.returncode == 1
    assert "hang" in done.stderr
    assert "ran over its 1s limit" in done.stderr
    assert re.search(r"^FAIL hang \d+s", done.stderr, re.MULTILINE)


def test_fail_fast_stops_the_others_and_never_calls_them_passed(fake: str) -> None:
    done = _steps(fake, "hang", "fail", flags=("--fail-fast",))
    assert done.returncode == 1
    assert re.search(r"^stop hang \d+s", done.stderr, re.MULTILINE)
    assert "gate FAIL fail" in done.stderr
    assert "not judged" in done.stderr
    assert "gate FAIL fail hang" not in done.stderr


def test_the_release_gate_refuses_fail_fast(fake: str) -> None:
    done = _steps(fake, "ok", flags=("--fail-fast", "--all"))
    assert done.returncode == 2


def test_fail_fast_is_reachable_through_the_environment(fake: str) -> None:
    done = _steps(fake, "hang", "fail", GATE_FAIL_FAST="1")
    assert re.search(r"^stop hang \d+s", done.stderr, re.MULTILINE)


def test_a_recipe_that_itself_exits_125_is_a_failure_not_a_stop(fake: str) -> None:
    done = _steps(fake, "x125", "ok")
    assert done.returncode == 1
    assert "gate FAIL x125" in done.stderr
    assert "not judged" not in done.stderr


def test_a_step_the_gate_could_not_run_fails_and_the_report_survives(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> tuple[int, bool]:
        message = "disk full"
        raise RuntimeError(message)

    monkeypatch.setattr("any_gate.steps._run_step", boom)
    report = run_steps(["a", "b"], env={})
    assert [step.returncode for step in report.steps] == [INTERNAL, INTERNAL]
    assert "disk full" in report.steps[0].log
    assert len(report.failed) == 2


def test_sigterm_stops_every_steps_tree(fake: str, tmp_path: Path) -> None:
    fifo = tmp_path / "pid"
    os.mkfifo(fifo)
    cmd = [sys.executable, "-m", "any_gate", "steps", "--runner", fake, "pidhang"]
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, env={**os.environ, "MEET": str(tmp_path)})
    with fifo.open() as started:  # blocks until the step wrote its pid: it is running
        pid = int(started.read())
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=30)
    assert proc.stderr is not None
    proc.stderr.close()
    with pytest.raises(ProcessLookupError):  # the gate waited for the stop: nothing is left behind
        os.kill(pid, 0)


def test_a_failed_thread_start_stops_the_started_steps_and_does_not_hang(monkeypatch: pytest.MonkeyPatch) -> None:
    started = threading.Event()
    release = threading.Event()
    calls = 0
    real = threading.Thread.start

    def start(self: threading.Thread) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            message = "can't start new thread"
            raise RuntimeError(message)
        real(self)

    monkeypatch.setattr(threading.Thread, "start", start)

    def one(_name: str) -> None:
        started.set()
        release.wait(10)

    stopper = threading.Event()
    threading.Thread(target=lambda: (stopper.wait(10), release.set()), daemon=True).start()
    with pytest.raises(RuntimeError):
        _run_threads(["a", "b"], one, stopper)
    assert stopper.is_set()


def test_a_false_value_leaves_fail_fast_off(fake: str) -> None:
    done = _steps(fake, "slow", "fail", GATE_FAIL_FAST="0")
    assert "not judged" not in done.stderr


def test_a_step_named_twice_is_refused(fake: str) -> None:
    assert _steps(fake, "ok", "ok").returncode == 2


def test_every_step_says_in_one_line_why_it_runs(fake: str) -> None:
    done = _steps(fake, "ok", "skip")
    assert "ok   ok 0s | declares no inputs\n" in done.stderr
    assert "skipped lint: no file changed\n" in done.stderr
