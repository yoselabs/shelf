"""``capture_bytes``: exact bytes, stdin input, the 124 timeout and the bounded drain, on real children."""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING, Any

import pytest
from stream_proc import alive, capture, capture_bytes

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

PY = sys.executable


def py(code: str) -> list[str]:
    return [PY, "-c", code]


def test_non_utf8_and_crlf_round_trip_exactly() -> None:
    payload = b"a\xff\xfe\r\nb\rc\n\x00"
    code = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()); sys.stderr.buffer.write(b'e\\xff\\r\\n')"
    got = capture_bytes(py(code), input=payload)
    assert (got.exit, got.out, got.err, got.timed_out) == (0, payload, b"e\xff\r\n", False)


def test_exit_code_and_signal_death() -> None:
    assert capture_bytes(py("import sys; sys.exit(3)")).exit == 3
    assert capture_bytes(py("import os,signal; os.kill(os.getpid(), signal.SIGKILL)")).exit == -9


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
        capture_bytes(py("pass"), input=b"x", stdin=None)


def test_capture_false_inherits_stdout_and_returns_empty() -> None:
    host = subprocess.run(
        [
            PY,
            "-c",
            (
                "from stream_proc import capture_bytes\n"
                "g = capture_bytes(['sh', '-c', 'echo loud; echo quiet >&2'], capture=False)\n"
                "print(g.exit, g.out, g.err)"
            ),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    assert host.stdout.split(b"\n") == [b"loud", b"0 b'' b''", b""]
    assert host.stderr == b"quiet\n"


def test_stdin_devnull_reads_eof_but_inherit_reads_ours() -> None:
    code = "import sys; print(len(sys.stdin.buffer.read()))"
    assert capture_bytes(py(code)).out == b"0\n"
    host = subprocess.run(
        [
            PY,
            "-c",
            (
                "from stream_proc import capture_bytes; import sys\n"
                f"print(capture_bytes([sys.executable, '-c', {code!r}], stdin=None).out.decode())"
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
        run(["sleep", "60"])
    assert len(sigterm_during_spawn) == 1
    assert not alive(sigterm_during_spawn[0])
