"""``capture_bytes``: exact bytes, stdin input, the 124 timeout and the bounded drain, on real children."""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING, Any

import pytest
from stream_proc import alive, capture, capture_bytes, run_inherited
from stream_proc.hold import MeasuredPopen

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

PY = sys.executable


def py(code: str) -> list[str]:
    return [PY, "-c", code]


def test_non_utf8_and_crlf_round_trip_exactly() -> None:
    payload = b"a\xff\xfe\r\nb\rc\n\x00"
    code = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()); sys.stderr.buffer.write(b'e\\xff\\r\\n')"
    got = capture_bytes(py(code), input=payload, timeout=30)
    assert (got.exit, got.out, got.err, got.timed_out) == (0, payload, b"e\xff\r\n", False)


def test_exit_code_and_signal_death() -> None:
    assert capture_bytes(py("import sys; sys.exit(3)"), timeout=30).exit == 3
    assert capture_bytes(py("import os,signal; os.kill(os.getpid(), signal.SIGKILL)"), timeout=30).exit == -9


def test_large_input_with_large_output_does_not_deadlock() -> None:
    code = "import sys; d=sys.stdin.buffer.read(); sys.stdout.buffer.write(d); sys.stderr.buffer.write(d)"
    data = b"x" * 3_000_000
    got = capture_bytes(py(code), input=data, timeout=30)
    assert (got.out, got.err) == (data, data)


def test_echo_while_reading_input_does_not_deadlock() -> None:
    # the child writes output before it has read all of its input
    code = "import sys\nwhile (c := sys.stdin.buffer.read(65536)):\n    sys.stdout.buffer.write(c); sys.stdout.buffer.flush()"
    data = b"y" * 2_000_000
    assert capture_bytes(py(code), input=data, timeout=30).out == data


def test_timeout_stops_a_setsid_grandchild_and_keeps_partial_bytes() -> None:
    code = (
        "import subprocess,sys,time\n"
        "g = subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],"
        " start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "sys.stdout.buffer.write(b'part\\xff\\r\\n'); sys.stdout.flush(); sys.stderr.write('e'); sys.stderr.flush()\n"
        "time.sleep(60)"
    )
    t0 = time.monotonic()
    got = capture_bytes(py(code), timeout=3.0, grace=1)
    assert (got.exit, got.timed_out) == (124, True)
    assert got.out == b"part\xff\r\n"
    assert got.err == b"e"
    assert got.survivors == ()
    assert time.monotonic() - t0 < 30


def test_a_timed_out_setsid_grandchild_is_dead() -> None:
    code = (
        "import subprocess,sys,time\n"
        "g = subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'], start_new_session=True,"
        " stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "print(g.pid, flush=True); time.sleep(60)"
    )
    got = capture_bytes(py(code), timeout=3.0, grace=1)
    assert got.timed_out
    assert not alive(int(got.out.split()[0]))


def test_timeout_kills_a_grandchild_that_stayed_in_the_group() -> None:
    code = (
        "import subprocess,sys,time\n"
        "k = subprocess.Popen(['sleep', '60'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "print(k.pid, flush=True); time.sleep(60)"
    )
    got = capture_bytes(py(code), timeout=1.5, grace=1)
    assert (got.exit, got.timed_out, got.survivors) == (124, True, ())
    assert not alive(int(got.out.split()[0]))


def test_a_normal_exit_with_a_pipe_holder_is_not_a_timeout() -> None:
    # sh exits 0 at once; its background sleep keeps the pipe open. The result waits `drain`, not 30 s, and is not a timeout.
    t0 = time.monotonic()
    got = capture_bytes(["sh", "-c", "sleep 30 & echo hi"], timeout=20, drain=1.0)
    assert (got.exit, got.timed_out, got.out) == (0, False, b"hi\n")
    assert time.monotonic() - t0 < 15


def test_the_drain_bounds_a_pipe_holder_outside_the_tree() -> None:
    # a reparented, setsid'd stranger (not under the child when the stop looks) holds stdout open for 12 s
    code = "import os,sys; sys.stdout.write('hi\\n'); sys.stdout.flush(); os.setsid(); os.write(2, b'x'); import time; time.sleep(12)"
    script = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{code!r}])"
    t0 = time.monotonic()
    got = capture_bytes([PY, "-c", script], timeout=30, drain=1.0)
    took = time.monotonic() - t0
    assert (got.exit, got.timed_out) == (0, False)
    assert got.out == b"hi\n"
    assert took < 10  # bounded by drain, not by the holder's 12 s


def test_an_early_exit_child_with_large_unwritten_input_is_not_an_error() -> None:
    got = capture_bytes(py("import sys; sys.stdout.write('done')"), input=b"z" * 5_000_000, timeout=30)
    assert (got.exit, got.out, got.timed_out) == (0, b"done", False)


def test_input_and_stdin_together_are_refused() -> None:
    with pytest.raises(ValueError, match="not both"):
        capture_bytes(py("pass"), input=b"x", stdin=None, timeout=30)


def test_run_inherited_writes_to_our_streams_and_returns_the_exit() -> None:
    host = subprocess.run(
        [
            PY,
            "-c",
            ("from stream_proc import run_inherited\nprint(run_inherited(['sh', '-c', 'echo loud; echo quiet >&2; exit 3'], timeout=30))"),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    assert host.stdout.split(b"\n") == [b"loud", b"3", b""]
    assert host.stderr == b"quiet\n"


def test_stdin_devnull_reads_eof_but_inherit_reads_ours() -> None:
    code = "import sys; print(len(sys.stdin.buffer.read()))"
    assert capture_bytes(py(code), timeout=30).out == b"0\n"
    host = subprocess.run(
        [
            PY,
            "-c",
            (
                "from stream_proc import capture_bytes; import sys\n"
                f"print(capture_bytes([sys.executable, '-c', {code!r}], stdin=None, timeout=30).out.decode())"
            ),
        ],
        input=b"abcde",
        capture_output=True,
        check=True,
        timeout=30,
    )
    assert host.stdout == b"5\n\n"


class BoomError(Exception):
    pass


@pytest.fixture
def sigterm_during_spawn(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[int]]:
    """Popen delivers SIGTERM right after the real spawn; the handler raises ``BoomError``. Yields the spawned pids."""
    pids: list[int] = []
    real_init = subprocess.Popen.__init__

    def init(self: subprocess.Popen[bytes], *args: Any, **kwargs: Any) -> None:
        real_init(self, *args, **kwargs)
        pids.append(self.pid)
        signal.raise_signal(signal.SIGTERM)

    def handler(signum: int, frame: object) -> None:
        raise BoomError

    old = signal.signal(signal.SIGTERM, handler)
    monkeypatch.setattr(subprocess.Popen, "__init__", init)
    try:
        yield pids
    finally:
        signal.signal(signal.SIGTERM, old)


@pytest.mark.parametrize("run", [capture_bytes, capture])
def test_raising_sigterm_handler_during_spawn_propagates_and_child_is_gone(
    sigterm_during_spawn: list[int], run: Callable[..., Any]
) -> None:
    with pytest.raises(BoomError):
        run(["sleep", "60"], timeout=30)
    assert len(sigterm_during_spawn) == 1
    assert not alive(sigterm_during_spawn[0])


def test_run_inherited_stops_the_tree_on_a_timeout_and_reports_124() -> None:
    assert run_inherited(py("import time; time.sleep(30)"), timeout=0.3, grace=0.5) == 124


def _hog_code(mib: int) -> str:
    return f"b = bytearray({mib} * 1024 * 1024); b[::4096] = b'x' * len(b[::4096])"


def _peaks(*codes: str) -> list[int]:
    """``peak_rss`` of each command, captured one after another from a fresh small interpreter.

    Linux hands a child its parent's resident high-water mark, so the parent must not be this (large, long-lived,
    xdist) test worker: its own size would be the floor of every number measured.
    """
    script = "import sys; from stream_proc import capture_bytes\n" + "".join(
        f"print(capture_bytes([sys.executable, '-c', {code!r}], timeout=30).peak_rss)\n" for code in codes
    )
    out = subprocess.run([PY, "-c", script], capture_output=True, text=True, check=True, timeout=120).stdout
    return [int(n) for n in out.split()]


def test_peak_rss_is_the_childs_own_high_water_mark_in_bytes() -> None:
    small, big = _peaks("pass", _hog_code(200))
    assert big >= 200 * 1024 * 1024
    assert big < 600 * 1024 * 1024
    assert small < big / 2


def test_peak_rss_is_per_child_not_the_callers_children_total() -> None:
    _, small = _peaks(_hog_code(300), "pass")  # an earlier, bigger child must not show in the next one
    assert small < 100 * 1024 * 1024


def test_polling_a_measured_child_reaps_it_and_keeps_its_peak_rss() -> None:
    """``poll()`` must work on every CPython (3.15 dropped the private ``_waitpid`` argument) and measure too."""
    p = MeasuredPopen(py("pass"))
    deadline = time.monotonic() + 30
    while p.poll() is None:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    assert p.returncode == 0
    assert p.peak_rss is not None
    assert p.peak_rss > 0
