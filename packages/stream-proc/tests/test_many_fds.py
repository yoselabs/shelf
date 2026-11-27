"""A parent holding more descriptors than FD_SETSIZE (1024) still spawns and reads (select.select raised ValueError there)."""

from __future__ import annotations

import os
import resource
import sys

import pytest
from stream_proc import run
from stream_proc.registered import popen_registered

HELD = 1100


@pytest.fixture
def many_fds():
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    wanted = HELD + 200
    if soft != resource.RLIM_INFINITY and soft < wanted:
        resource.setrlimit(resource.RLIMIT_NOFILE, (wanted if hard == resource.RLIM_INFINITY else min(wanted, hard), hard))
    fds: list[int] = []
    try:
        while len(fds) < HELD:
            fds.append(os.open(os.devnull, os.O_RDONLY | os.O_CLOEXEC))
    except OSError:
        pytest.skip("cannot raise the descriptor limit")
    try:
        yield fds
    finally:
        for fd in fds:
            os.close(fd)
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))


def test_popen_registered_reads_with_high_descriptors(many_fds: list[int]) -> None:
    seen: list[object] = []
    child, _ = popen_registered([sys.executable, "-c", "print('hi')"], registered=seen.append, env=dict(os.environ))
    assert child.stdout is not None
    assert child.stdout.read() == b"hi\n"
    child.wait()
    assert child.stdout.fileno() > 1024
    child.stdout.close()
    if child.stdin:
        child.stdin.close()
    if child.stderr:
        child.stderr.close()


def test_run_pumps_output_with_high_descriptors(many_fds: list[int]) -> None:
    lines: list[str] = []
    result = run([sys.executable, "-c", "print('hi')"], env=dict(os.environ), on_stdout=lines.append, timeout=20)
    assert result.returncode == 0
    assert "".join(lines) == "hi\n"
