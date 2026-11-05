"""``capture``: text output, exit codes, the 124 timeout and the heartbeat, on real children."""

from __future__ import annotations

import sys
import time

from stream_proc import alive, capture

PY = sys.executable


def py(code: str) -> list[str]:
    return [PY, "-c", code]


def test_output_and_exit_code_come_back_as_text() -> None:
    got = capture(py("import sys; print('héllo'); sys.stderr.write('bad\\n'); sys.exit(3)"))
    assert (got.exit, got.out, got.err, got.timed_out) == (3, "héllo\n", "bad\n", False)


def test_undecodable_bytes_are_replaced() -> None:
    got = capture(py("import sys; sys.stdout.buffer.write(b'a\\xffb')"))
    assert got.out == "a�b"


def test_a_timed_out_capture_reports_124_and_leaves_nothing_running() -> None:
    code = "import os,sys,time; print(os.getpid(), flush=True); time.sleep(60)"
    t0 = time.monotonic()
    got = capture(py(code), timeout=0.5, grace=1)
    assert (got.exit, got.timed_out) == (124, True)
    assert time.monotonic() - t0 < 10
    assert not alive(int(got.out.split()[0]))
    assert got.survivors == ()


def test_a_signal_death_is_a_negative_exit() -> None:
    got = capture(py("import os,signal; os.kill(os.getpid(), signal.SIGKILL)"))
    assert (got.exit, got.timed_out) == (-9, False)


def test_large_output_is_kept_whole() -> None:
    got = capture(py("[print('x' * 79) for _ in range(50000)]"))
    assert got.out.count("\n") == 50000


def test_tick_runs_while_the_child_lives_and_once_after() -> None:
    beats: list[float] = []
    got = capture(py("import time; time.sleep(1.0)"), tick=lambda: beats.append(time.monotonic()), poll_s=0.1)
    assert got.exit == 0
    assert len(beats) >= 3
    assert beats[-1] >= beats[-2]


def _boom() -> None:
    raise ZeroDivisionError


def test_a_raising_tick_does_not_lose_the_result() -> None:
    got = capture(py("print('kept')"), tick=_boom)
    assert (got.exit, got.out) == (0, "kept\n")


def test_a_timeout_stops_a_grandchild_that_left_the_group() -> None:
    code = (
        "import os,subprocess,sys,time\n"
        "g = subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'], start_new_session=True)\n"
        "print(g.pid, flush=True); time.sleep(60)\n"
    )
    got = capture(py(code), timeout=1.0, grace=1)
    assert got.exit == 124
    assert not alive(int(got.out.split()[0]))
