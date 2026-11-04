"""Real processes: a race that never exceeds the limit, and a kill -9 that frees its unit."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import time
from typing import TYPE_CHECKING

import pytest

from any_lease import Leases, LeaseTimeoutError

if TYPE_CHECKING:
    from pathlib import Path

LIMIT = 2
RACERS = 6

# Waits for the go file (the barrier), takes a unit, records how many are inside by counting marker files, leaves.
_RACER = textwrap.dedent(
    """
    import os, sys, time
    from pathlib import Path
    from any_lease import Leases
    root, work, me = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    while not (work / "go").exists():
        time.sleep(0.005)
    with Leases(root).acquire("res", int(sys.argv[4]), poll=0.01, label=me):
        (work / f"in-{me}").touch()
        seen = len(list(work.glob("in-*")))
        time.sleep(0.15)
        (work / f"in-{me}").unlink()
    (work / f"seen-{me}").write_text(str(seen))
    """
)

# Takes a unit, tells the parent, then sleeps until killed.
_HOLDER = textwrap.dedent(
    """
    import sys, time
    from pathlib import Path
    from any_lease import Leases
    held = Leases(Path(sys.argv[1])).acquire("res", 1)
    print(held.slot, flush=True)
    time.sleep(60)
    """
)


def test_more_processes_than_units_never_exceed_the_limit(tmp_path: Path) -> None:
    root, work = tmp_path / "locks", tmp_path / "work"
    work.mkdir()
    procs = [subprocess.Popen([sys.executable, "-c", _RACER, str(root), str(work), str(i), str(LIMIT)]) for i in range(RACERS)]
    time.sleep(0.5)  # let every racer reach the barrier
    (work / "go").touch()
    assert [p.wait(timeout=60) for p in procs] == [0] * RACERS
    seen = [int(f.read_text()) for f in work.glob("seen-*")]
    assert len(seen) == RACERS
    assert max(seen) == LIMIT  # the limit was reached, never passed


def test_kill_nine_of_a_holder_frees_its_unit_within_one_poll(tmp_path: Path) -> None:
    root = tmp_path / "locks"
    proc = subprocess.Popen([sys.executable, "-c", _HOLDER, str(root)], stdout=subprocess.PIPE, text=True)
    assert proc.stdout is not None
    assert proc.stdout.readline().strip() == "0"
    leases = Leases(root)
    assert [o.holder.pid for o in leases.holders("res", 1) if o.holder] == [proc.pid]
    proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=10)
    got = leases.acquire("res", 1, timeout=0)  # the kernel freed it when the process was reaped: the first poll wins
    assert got.slot == 0
    got.release()


# Takes a unit, forks a child that keeps the descriptor (no exec), prints the child's pid, sleeps.
_FORKER = textwrap.dedent(
    """
    import os, sys, time
    from pathlib import Path
    from any_lease import Leases
    held = Leases(Path(sys.argv[1])).acquire("res", 1)
    child = os.fork()
    if child == 0:
        time.sleep(60)
        os._exit(0)
    print(child, flush=True)
    time.sleep(60)
    """
)

# Takes a unit and lets it go, then stays alive: its record outlives the unit.
_RELEASER = textwrap.dedent(
    """
    import sys, time
    from pathlib import Path
    from any_lease import Leases
    Leases(Path(sys.argv[1])).acquire("res", 1, label="gone").release()
    print("done", flush=True)
    time.sleep(60)
    """
)


def test_a_forked_child_keeps_the_unit_after_the_holder_is_killed(tmp_path: Path) -> None:
    root = tmp_path / "locks"
    proc = subprocess.Popen([sys.executable, "-c", _FORKER, str(root)], stdout=subprocess.PIPE, text=True)
    assert proc.stdout is not None
    child = int(proc.stdout.readline())
    proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=10)
    try:
        assert len(Leases(root).holders("res", 1)) == 1  # only a raw fork does this: Python's descriptors are not inherited by exec
        with pytest.raises(LeaseTimeoutError):
            Leases(root).acquire("res", 1, timeout=0)
    finally:
        os.kill(child, signal.SIGKILL)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and Leases(root).holders("res", 1):
        time.sleep(0.05)
    Leases(root).acquire("res", 1, timeout=0).release()


def test_a_released_unit_is_free_though_its_holder_record_names_a_live_pid(tmp_path: Path) -> None:
    root = tmp_path / "locks"
    proc = subprocess.Popen([sys.executable, "-c", _RELEASER, str(root)], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "done"
        assert Leases(root).holders("res", 1) == ()
    finally:
        proc.kill()
        proc.wait(timeout=10)
