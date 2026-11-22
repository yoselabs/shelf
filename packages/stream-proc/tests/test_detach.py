"""``spawn_detached``: a child that outlives its caller and never holds the caller's pipes."""

from __future__ import annotations

import subprocess
import sys
import time
from typing import TYPE_CHECKING

import pytest
from stream_proc import alive, proctable, spawn_detached, stop_pid

if TYPE_CHECKING:
    from pathlib import Path

needs_proc = pytest.mark.skipif(not proctable.has_table(), reason="needs a process table")


@needs_proc
def test_the_child_runs_detached_and_writes_to_the_log(tmp_path: Path) -> None:
    log = tmp_path / "logs" / "w.log"
    d = spawn_detached([sys.executable, "-c", "print('hello', flush=True); import time; time.sleep(60)"], cwd=tmp_path, env={}, log=log)
    try:
        assert alive(d.pid, d.start)
        deadline = time.monotonic() + 10
        while "hello" not in (log.read_text() if log.exists() else "") and time.monotonic() < deadline:
            time.sleep(0.05)
        assert "hello" in log.read_text()
    finally:
        assert stop_pid(d.pid, d.start, grace=1) == ()
    assert not alive(d.pid, d.start)


@needs_proc
def test_a_reader_of_our_stdout_is_not_kept_waiting_by_the_child(tmp_path: Path) -> None:
    launcher = (
        "import sys\nfrom pathlib import Path\nfrom stream_proc import spawn_detached\n"
        "d = spawn_detached([sys.executable, '-c', 'import time; time.sleep(60)'], cwd=Path('.'), env={}, log=Path(sys.argv[1]))\n"
        "print(d.pid, d.start)\n"
    )
    t0 = time.monotonic()
    done = subprocess.run([sys.executable, "-c", launcher, str(tmp_path / "x.log")], capture_output=True, text=True, timeout=20, check=True)
    assert time.monotonic() - t0 < 10
    pid, start = done.stdout.split(maxsplit=1)
    try:
        assert alive(int(pid), start.strip())
    finally:
        stop_pid(int(pid), start.strip(), grace=1)


def test_a_missing_program_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        spawn_detached(["/no/such/program"], cwd=tmp_path, env={}, log=tmp_path / "l.log")
