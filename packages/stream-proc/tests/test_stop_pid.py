"""``stop_pid`` / ``PidHandle``: a process we did not spawn is stopped only while its start token matches."""

from __future__ import annotations

import subprocess
import sys

import pytest
from stream_proc import PidHandle, alive, proc_start, proctable, stop_pid

needs_proc = pytest.mark.skipif(not proctable.has_table(), reason="needs a process table")


def sleeper() -> subprocess.Popen[bytes]:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)


@needs_proc
def test_an_unrelated_pid_with_a_wrong_start_token_is_not_stopped() -> None:
    p = sleeper()
    try:
        assert stop_pid(p.pid, "0.0-not-its-token", grace=0.5) == ()
        assert p.poll() is None
        assert alive(p.pid, proc_start(p.pid))
    finally:
        p.kill()
        p.wait()


@needs_proc
def test_the_right_token_stops_the_process_and_its_tree() -> None:
    p = sleeper()
    try:
        assert stop_pid(p.pid, proc_start(p.pid), grace=1) == ()
        assert p.wait(timeout=5) == -15
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


@needs_proc
def test_no_token_given_takes_the_current_one() -> None:
    p = sleeper()
    try:
        assert stop_pid(p.pid, grace=1) == ()
        assert p.wait(timeout=5) is not None
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


def test_a_gone_pid_is_a_no_op() -> None:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    assert stop_pid(p.pid, "1.2", grace=0.5) == ()


@needs_proc
def test_handle_reads_a_mismatched_token_as_gone() -> None:
    p = sleeper()
    try:
        assert PidHandle(p.pid, "0.0-wrong").poll() == 0
        h = PidHandle(p.pid)
        assert h.poll() is None
        p.kill()
        p.wait()
        assert h.wait(timeout=2) == 0
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
