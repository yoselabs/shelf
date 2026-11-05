"""``capture_bytes``: exact bytes, stdin input, the 124 timeout and the bounded drain, on real children."""

from __future__ import annotations

import subprocess
import sys
import time

from stream_proc import alive, capture_bytes

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
    got = capture_bytes(py(code), timeout=1.0, grace=1)
    assert (got.exit, got.timed_out) == (124, True)
    assert got.out == b"part\xff\r\n"
    assert got.err == b"e"
    assert got.survivors == ()
    assert time.monotonic() - t0 < 10


def test_a_timed_out_setsid_grandchild_is_dead() -> None:
    code = (
        "import subprocess,sys,time\n"
        "g = subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'], start_new_session=True,"
        " stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "print(g.pid, flush=True); time.sleep(60)"
    )
    got = capture_bytes(py(code), timeout=1.0, grace=1)
    assert got.timed_out
    assert not alive(int(got.out.split()[0]))


def test_an_unrelated_holder_of_the_pipe_does_not_hang_the_drain() -> None:
    # a setsid grandchild that closes nothing and ignores SIGTERM keeps the pipe open past the stop
    code = (
        "import subprocess,sys,time\n"
        "print('hi', flush=True)\n"
        "subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN);"
        " time.sleep(8)'], start_new_session=True)\n"
        "time.sleep(60)"
    )
    t0 = time.monotonic()
    got = capture_bytes(py(code), timeout=2.0, grace=0.5, drain=2.0)
    took = time.monotonic() - t0
    assert got.timed_out
    assert got.out == b"hi\n"
    assert took < 7


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
                f"print(capture_bytes([sys.executable, '-c', {code!r}], stdin='inherit').out.decode())"
            ),
        ],
        input=b"abcde",
        capture_output=True,
        check=True,
        timeout=30,
    )
    assert host.stdout == b"5\n\n"
