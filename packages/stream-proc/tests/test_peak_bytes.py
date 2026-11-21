"""The rusage unit has one owner: `peak_bytes` turns a wait4 rusage into bytes on either OS."""

from __future__ import annotations

import os
import subprocess
import sys

from stream_proc import peak_bytes


def test_peak_bytes_is_the_waited_childs_resident_set_in_bytes() -> None:
    child = subprocess.Popen([sys.executable, "-c", "x = bytearray(60 * 1024 * 1024)"])
    _, _, usage = os.wait4(child.pid, 0)
    assert 60 * 1024 * 1024 < peak_bytes(usage) < 4 * 1024**3
