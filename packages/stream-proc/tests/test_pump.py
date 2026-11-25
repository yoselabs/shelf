"""Pump: the readers, the feeder and the pipes' lifetime of one held child. No close under a reader, no hang on a held pipe."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from typing import TYPE_CHECKING

import pytest
from stream_proc import Pump, PumpStuckError

if TYPE_CHECKING:
    from collections.abc import Iterator

PY = sys.executable


_spawned: list[subprocess.Popen[bytes]] = []


@pytest.fixture(autouse=True)
def _reap_spawned() -> Iterator[None]:
    yield
    while _spawned:
        child = _spawned.pop()
        child.kill()
        child.wait()
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream is not None:
                stream.close()


def spawn(code: str, *, stdin: bool = False) -> subprocess.Popen[bytes]:
    child = subprocess.Popen(
        [PY, "-c", code], stdin=subprocess.PIPE if stdin else subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    _spawned.append(child)
    return child


def closed(p: subprocess.Popen[bytes]) -> bool:
    return all(s is None or s.closed for s in (p.stdin, p.stdout, p.stderr))


def test_each_stream_goes_to_its_callback_and_release_closes_the_pipes() -> None:
    p = spawn("import sys\nprint('o1')\nprint('e1', file=sys.stderr)\nsys.stdout.write('torn')")
    out: list[bytes] = []
    err: list[bytes] = []
    pump = Pump(p, on_stdout=out.append, on_stderr=err.append)
    pump.start()
    assert pump.drain(10)
    p.wait()
    assert not closed(p)  # draining ends the readers, it does not close
    pump.release()
    assert (out, err) == ([b"o1\n", b"torn"], [b"e1\n"])
    assert closed(p)
    assert pump.splits == 0


def test_a_grandchild_holding_the_pipe_neither_hangs_the_owner_nor_gets_it_closed_under_a_reader() -> None:
    code = (
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(4)'], start_new_session=True)\n"
        "print('x', flush=True)\n"
    )
    p = spawn(code)
    seen: list[bytes] = []
    inside = threading.Event()

    def hear(raw: bytes) -> None:
        inside.set()
        seen.append(raw)

    pump = Pump(p, on_stdout=hear)
    pump.start()
    p.wait()
    assert inside.wait(5)
    t0 = time.monotonic()
    assert not pump.drain(0.3)  # the grandchild keeps EOF away: not drained, and it says so
    pump.release()
    assert time.monotonic() - t0 < 2.0  # the reader polls: it ends without EOF, so the owner is never pinned by the stranger
    assert closed(p)
    assert seen == [b"x\n"]


def test_release_waits_for_a_reader_still_inside_its_callback() -> None:
    p = spawn("print('x', flush=True)\nimport time; time.sleep(30)")
    entered, gate = threading.Event(), threading.Event()

    def block(_raw: bytes) -> None:
        entered.set()
        gate.wait(10)

    pump = Pump(p, on_stdout=block)
    pump.start()
    assert entered.wait(5)
    releasing = threading.Thread(target=pump.release)
    releasing.start()
    time.sleep(0.4)  # long past a reader's poll: a release that closed after a timeout would be done by now
    assert releasing.is_alive()
    assert not p.stdout.closed  # type: ignore[union-attr]
    gate.set()
    releasing.join(5)
    assert not releasing.is_alive()
    assert closed(p)
    p.kill()
    p.wait()


def test_the_feeder_delivers_the_input_and_the_end_of_it() -> None:
    p = spawn("import sys\nsys.stdout.write(sys.stdin.read().upper())", stdin=True)
    out: list[bytes] = []
    pump = Pump(p, on_stdout=out.append, stdin=b"hello\nworld\n")
    pump.start()
    assert pump.drain(10)
    pump.release()
    p.wait()
    assert out == [b"HELLO\n", b"WORLD\n"]


def test_a_child_that_exits_without_reading_its_input_is_not_an_error() -> None:
    p = spawn("pass", stdin=True)
    pump = Pump(p, stdin=b"x" * 4_000_000)
    pump.start()
    assert pump.drain(10)
    pump.release()
    assert p.wait() == 0
    assert closed(p)


def test_a_child_that_never_reads_does_not_pin_the_owner() -> None:
    p = spawn("import time; time.sleep(30)", stdin=True)
    pump = Pump(p, stdin=b"x" * 4_000_000)  # the pipe fills: the feeder waits for a reader that never comes
    pump.start()
    t0 = time.monotonic()
    pump.release()
    assert time.monotonic() - t0 < 2.0
    assert closed(p)
    p.kill()
    p.wait()


def test_a_very_long_line_reaches_the_callback_in_capped_pieces() -> None:
    p = spawn("import sys\nsys.stdout.write('a' * 3_000_000 + '\\nshort\\n')")
    out: list[bytes] = []
    pump = Pump(p, on_stdout=out.append, max_line=1_000_000)
    pump.start()
    assert pump.drain(20)
    pump.release()
    assert [len(piece) for piece in out] == [1_000_000, 1_000_000, 1_000_000, 1, 6]
    assert b"".join(out) == b"a" * 3_000_000 + b"\nshort\n"
    assert pump.splits == 3


def test_a_line_exactly_under_the_cap_is_whole() -> None:
    p = spawn("print('b' * 98)")
    out: list[bytes] = []
    pump = Pump(p, on_stdout=out.append, max_line=100)
    pump.start()
    assert pump.drain(10)
    pump.release()
    assert out == [b"b" * 98 + b"\n"]
    assert pump.splits == 0


def test_a_failing_callback_is_called_once_and_its_error_is_raised_by_release_after_full_teardown() -> None:
    p = spawn("print('1')\nprint('2')")
    seen: list[bytes] = []
    failure = RuntimeError("first")

    def boom(raw: bytes) -> None:
        seen.append(raw)
        raise failure

    pump = Pump(p, on_stdout=boom)
    pump.start()
    assert pump.drain(10)  # the reading went on to EOF
    with pytest.raises(RuntimeError) as caught:
        pump.release()
    assert caught.value is failure
    assert seen == [b"1\n"]  # a callback that raised is not invoked again
    assert closed(p)  # the teardown finished before the raise
    pump.release()  # the error is raised once
    p.wait()


def test_the_first_error_of_the_pump_is_the_one_kept() -> None:
    p = spawn("import sys, time\nprint('o', flush=True)\ntime.sleep(0.4)\nprint('e', file=sys.stderr, flush=True)")
    first, second = RuntimeError("stdout"), ValueError("stderr")

    def fail_out(_raw: bytes) -> None:
        raise first

    def fail_err(_raw: bytes) -> None:
        raise second

    pump = Pump(p, on_stdout=fail_out, on_stderr=fail_err)
    pump.start()
    assert pump.drain(10)
    with pytest.raises(RuntimeError) as caught:
        pump.release()
    assert caught.value is first
    p.wait()


def test_a_child_writing_a_lot_after_the_callback_failed_is_still_drained() -> None:
    code = "import sys\nfor _ in range(200):\n    sys.stdout.write('x' * 50000 + '\\n')\n    sys.stderr.write('y' * 50000 + '\\n')\n"
    p = spawn(code)
    calls: list[int] = []

    def boom(_raw: bytes) -> None:
        calls.append(1)
        raise RuntimeError

    pump = Pump(p, on_stdout=boom, on_stderr=boom)
    pump.start()
    assert pump.drain(30)  # 20 MB past two failed callbacks: a full pipe would block the child for good
    with pytest.raises(RuntimeError):
        pump.release()
    assert p.wait(10) == 0
    assert len(calls) <= 2


def test_a_failing_touch_is_not_called_again_and_its_error_is_raised() -> None:
    p = spawn("print('1')\nprint('2')")
    touched: list[int] = []
    out: list[bytes] = []

    def touch() -> None:
        touched.append(1)
        msg = "touch"
        raise OSError(msg)

    pump = Pump(p, on_stdout=out.append, touch=touch)
    pump.start()
    assert pump.drain(10)
    with pytest.raises(OSError, match="touch"):
        pump.release()
    assert out == [b"1\n", b"2\n"]
    assert touched == [1]
    p.wait()


def test_a_callback_that_never_returns_makes_release_raise_pump_stuck_and_leaves_the_pipes_open() -> None:
    p = spawn("print('x', flush=True)\nimport time; time.sleep(30)")
    entered, gate = threading.Event(), threading.Event()

    def block(_raw: bytes) -> None:
        entered.set()
        gate.wait(10)

    pump = Pump(p, on_stdout=block, stuck_after=0.3)
    pump.start()
    assert entered.wait(5)
    t0 = time.monotonic()
    with pytest.raises(PumpStuckError) as caught:
        pump.release()
    assert time.monotonic() - t0 < 3.0
    assert caught.value.running == ("on_stdout",)
    assert not p.stdout.closed  # type: ignore[union-attr]  # a close under the reader is the race: nothing was closed
    gate.set()
    pump.release()  # the callback returned: the teardown completes
    assert closed(p)
    p.kill()
    p.wait()


def test_touch_runs_when_bytes_arrive() -> None:
    p = spawn("print('x')")
    touched = threading.Event()
    pump = Pump(p, touch=touched.set)
    pump.start()
    assert pump.drain(10)
    pump.release()
    assert touched.is_set()


def test_release_without_start_closes_the_pipes_and_twice_is_fine() -> None:
    p = spawn("pass", stdin=True)
    pump = Pump(p)
    pump.release()
    pump.release()
    assert closed(p)
    p.wait()


def test_a_cap_below_one_is_refused() -> None:
    p = spawn("pass")
    try:
        with pytest.raises(ValueError, match="max_line"):
            Pump(p, max_line=0)
    finally:
        p.wait()
        for s in (p.stdout, p.stderr):
            s.close()  # type: ignore[union-attr]
