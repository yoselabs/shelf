"""Pump: the readers, the feeder and the pipes' lifetime of one held child. No close under a reader, no hang on a held pipe."""

from __future__ import annotations

import subprocess
import sys
import threading
import time

import pytest
from stream_proc import Pump

PY = sys.executable


def spawn(code: str, *, stdin: bool = False) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [PY, "-c", code], stdin=subprocess.PIPE if stdin else subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )


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


def test_a_failing_callback_does_not_stop_the_reading() -> None:
    p = spawn("print('1')\nprint('2')")
    seen: list[bytes] = []

    def boom(raw: bytes) -> None:
        seen.append(raw)
        raise RuntimeError

    pump = Pump(p, on_stdout=boom)
    pump.start()
    assert pump.drain(10)
    pump.release()
    assert seen == [b"1\n", b"2\n"]


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
