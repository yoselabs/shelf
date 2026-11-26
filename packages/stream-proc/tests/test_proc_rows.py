"""The process table rows carry what both ``ps`` parsers read: owner, group and resident memory, the same on Linux and macOS."""

from __future__ import annotations

import inspect
import os
import subprocess
import sys

from stream_proc import capture, group_rss, table

PY = sys.executable
_MB = 1024 * 1024
_KID = "b = bytearray(b'y' * (60 * 1024 * 1024)); print(1, flush=True); import time; time.sleep(30)"


def test_our_own_row_names_its_owner_group_and_memory() -> None:
    row = table()[os.getpid()]
    assert (row.uid, row.pgid) == (os.getuid(), os.getpgrp())
    assert row.rss > _MB  # bytes: a Python interpreter holds more than a megabyte


def test_group_rss_counts_every_process_of_the_group_in_bytes() -> None:
    code = (
        "import subprocess, sys, time\n"
        "hold = bytearray(b'x' * (60 * 1024 * 1024))\n"
        f"kid = subprocess.Popen([sys.executable, '-c', {_KID!r}], stdout=subprocess.PIPE)\n"
        "kid.stdout.readline()\n"
        "print('ready', flush=True)\n"
        "time.sleep(30)\n"
    )
    p = subprocess.Popen([PY, "-c", code], start_new_session=True, stdout=subprocess.PIPE)
    try:
        assert p.stdout is not None
        p.stdout.readline()
        assert group_rss(p.pid) > 100 * _MB  # both processes, one figure
        assert group_rss(p.pid, table()) > 100 * _MB
    finally:
        p.kill()
        p.wait()
        if p.stdout is not None:
            p.stdout.close()


def test_group_rss_of_an_empty_group_is_zero() -> None:
    assert group_rss(2**22 + 12345) == 0


def test_the_bounded_runs_refuse_to_run_without_a_timeout() -> None:
    timeout = inspect.signature(capture).parameters["timeout"]
    assert timeout.kind is inspect.Parameter.KEYWORD_ONLY
    assert timeout.default is inspect.Parameter.empty
