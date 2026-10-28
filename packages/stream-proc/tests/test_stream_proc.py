"""Real children (``python -c``, no shell): streaming, limits, the stop flag and the tree stop."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from typing import TYPE_CHECKING, Any

import pytest
import stream_proc
from stream_proc import Result, procfs, run, stop_tree
from stream_proc.hold import TermHold, popen_held

if TYPE_CHECKING:
    from collections.abc import Iterator

PY = sys.executable
needs_proc = pytest.mark.skipif(not procfs.has_proc(), reason="needs /proc")


def py(code: str) -> list[str]:
    return [PY, "-c", code]


def test_large_output_on_both_streams_does_not_deadlock() -> None:
    code = "import sys\nfor i in range(60000):\n    sys.stdout.write('o' * 80 + '\\n')\n    sys.stderr.write('e' * 80 + '\\n')\n"
    out: list[str] = []
    err: list[str] = []
    res = run(py(code), on_stdout=out.append, on_stderr=err.append, timeout=60)
    assert (res.returncode, res.timed_out, res.signal) == (0, None, None)
    assert len(out) == len(err) == 60000


def test_torn_last_line_is_flushed_and_exit_code_kept() -> None:
    out: list[str] = []
    res = run(py("import sys; sys.stdout.write('a\\nb'); sys.exit(3)"), on_stdout=out.append)
    assert out == ["a\n", "b"]
    assert res.returncode == 3


def test_result_names_the_child_for_good() -> None:
    res = run(py("pass"))
    assert isinstance(res, Result)
    assert res.pid == res.pgid > 1
    assert res.secs >= 0
    if procfs.has_proc():
        assert res.start


def test_a_failing_callback_does_not_stop_the_reading() -> None:
    seen: list[str] = []

    def bad(line: str) -> None:
        seen.append(line)
        raise RuntimeError

    res = run(py("print(1); print(2)"), on_stdout=bad)
    assert seen == ["1\n", "2\n"]
    assert res.returncode == 0


def test_wall_timeout_stops_the_child() -> None:
    res = run(py("import time; time.sleep(60)"), timeout=0.4, grace=1)
    assert res.timed_out == "wall"
    assert res.returncode is None
    assert res.signal == signal.SIGTERM
    assert res.survivors == ()


def test_idle_timeout_counts_silence_not_runtime() -> None:
    res = run(py("import time\nprint('x', flush=True)\ntime.sleep(60)"), idle=0.5, grace=1)
    assert res.timed_out == "idle"


def test_steady_output_keeps_an_idle_child_running() -> None:
    code = "import time\nfor _ in range(15):\n    print('x', flush=True)\n    time.sleep(0.1)\n"
    res = run(py(code), idle=0.6)
    assert (res.timed_out, res.returncode) == (None, 0)


def test_stop_flag_stops_the_child() -> None:
    flag = threading.Event()

    def on_line(line: str) -> None:
        flag.set()

    res = run(py("import time\nprint('up', flush=True)\ntime.sleep(60)"), on_stdout=on_line, stop=flag, grace=1)
    assert res.timed_out == "stopped"
    assert res.survivors == ()


def test_sigterm_ignoring_child_gets_sigkill() -> None:
    flag = threading.Event()
    code = "import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nprint('up', flush=True)\ntime.sleep(60)"
    res = run(py(code), on_stdout=lambda _l: flag.set(), stop=flag, grace=0.3)
    assert res.timed_out == "stopped"
    assert res.signal == signal.SIGKILL


GRANDCHILD = (
    "import subprocess, sys, time\n"
    "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)\n"
    "print(g.pid, flush=True)\n"
    "time.sleep(60)\n"
)


@needs_proc
def test_grandchild_in_its_own_session_is_dead_after_stop() -> None:
    flag = threading.Event()
    seen: list[int] = []

    def on_line(line: str) -> None:
        seen.append(int(line))
        flag.set()

    res = run(py(GRANDCHILD), on_stdout=on_line, stop=flag, grace=1)
    gpid = seen[0]
    assert res.survivors == ()
    assert not procfs.alive(gpid)
    assert os.getpgid(os.getpid()) != gpid


@needs_proc
def test_liveness_is_pid_reuse_safe() -> None:
    me = os.getpid()
    start = procfs.proc_start(me)
    assert start
    assert procfs.alive(me, start)
    assert not procfs.alive(me, start + "0")
    assert not procfs.alive(None)


def test_descendants_walks_a_table() -> None:
    def row(pid: int, ppid: int) -> procfs.Proc:
        return procfs.Proc(pid, ppid, pid, pid, "1", "S")

    rows = {r.pid: r for r in (row(2, 1), row(3, 2), row(4, 3), row(9, 8))}
    assert [r.pid for r in procfs.descendants(2, rows)] == [3, 4]


def test_stop_tree_never_signals_a_group_that_is_ours() -> None:
    p = subprocess.Popen(py("import time; time.sleep(60)"))  # shares our group
    try:
        assert stop_tree(p, grace=1) == ()
        assert p.returncode is not None
        os.kill(os.getpid(), 0)
    finally:
        p.kill()
        p.wait()


class StopSignalError(Exception):
    pass


@pytest.fixture
def raising_term() -> Iterator[None]:
    def handler(_s: int, _f: Any) -> None:
        raise StopSignalError

    old = signal.signal(signal.SIGTERM, handler)
    yield
    signal.signal(signal.SIGTERM, old)


def test_term_hold_defers_the_signal_until_replay(raising_term: None) -> None:
    with TermHold() as hold:
        os.kill(os.getpid(), signal.SIGTERM)  # would raise here without the hold
        assert hold.held
    with pytest.raises(StopSignalError):
        hold.replay()


def test_sigterm_between_fork_and_assignment_still_stops_the_child(raising_term: None, monkeypatch: pytest.MonkeyPatch) -> None:
    spawned: list[subprocess.Popen[Any]] = []
    real = subprocess.Popen

    def popen_then_term(*args: Any, **kwargs: Any) -> subprocess.Popen[Any]:
        child = real(*args, **kwargs)
        spawned.append(child)
        os.kill(os.getpid(), signal.SIGTERM)  # lands before the caller holds the Popen
        return child

    monkeypatch.setattr(subprocess, "Popen", popen_then_term)
    with pytest.raises(StopSignalError):
        run(py("import time; time.sleep(60)"), grace=1)
    monkeypatch.undo()
    child = spawned[0]
    assert child.returncode is not None  # stopped and reaped, not left running
    assert not procfs.alive(child.pid) or not procfs.has_proc()


def test_popen_held_returns_the_child_and_its_hold() -> None:
    p, hold = popen_held(py("pass"))
    hold.replay()
    assert p.wait() == 0


def test_public_names() -> None:
    assert set(stream_proc.__all__) >= {"run", "Result", "stop_tree", "alive", "proc_start", "TermHold", "popen_held"}


def test_a_deadline_is_met_roughly() -> None:
    t = time.monotonic()
    run(py("import time; time.sleep(60)"), timeout=0.3, grace=1)
    assert time.monotonic() - t < 5
