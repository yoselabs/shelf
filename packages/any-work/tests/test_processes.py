"""Real processes: no key is claimed twice, a killed claimer frees its key, ten drainers lose and repeat nothing."""

from __future__ import annotations

import signal
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import IO

from any_work import Item, Status, Work

_HERE = Path(__file__).parent


def start_claimer(db: Path, leases: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-I", str(_HERE / "_proc_claim.py"), str(db), str(leases)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )


def said(proc: subprocess.Popen[str]) -> str:
    out: IO[str] | None = proc.stdout
    assert out is not None
    return out.readline().strip()


def stop(proc: subprocess.Popen[str]) -> None:
    assert proc.stdin is not None
    proc.stdin.close()
    proc.wait(timeout=30)


def test_two_processes_never_claim_the_same_key(tmp_path: Path) -> None:
    db, leases = tmp_path / "w.db", tmp_path / "l"
    work = Work(db, leases)
    work.add([Item("only")])
    first, second = start_claimer(db, leases), start_claimer(db, leases)
    answers = sorted([said(first), said(second)])
    stop(first)
    stop(second)
    work.close()
    assert answers == ["CLAIMED only", "NONE"]


def test_a_claimer_killed_with_sigkill_frees_its_key_at_once(tmp_path: Path) -> None:
    db, leases = tmp_path / "w.db", tmp_path / "l"
    work = Work(db, leases)
    work.add([Item("k")])
    child = start_claimer(db, leases)
    assert said(child) == "CLAIMED k"
    assert work.claim() is None  # alive: held
    child.send_signal(signal.SIGKILL)
    child.wait(timeout=30)  # the kernel has dropped the flock once the process is reaped
    again = work.claim()
    assert again is not None
    assert (again.key, again.attempts) == ("k", 0)  # the dead claimer's attempt was never recorded
    again.release()
    work.close()


def test_ten_processes_drain_two_hundred_items_none_twice_none_lost(tmp_path: Path) -> None:
    db, leases, log = tmp_path / "w.db", tmp_path / "l", tmp_path / "ran.log"
    work = Work(db, leases)
    keys = [f"item-{i:03}" for i in range(200)]
    work.add([Item(k) for k in keys])
    procs = [
        subprocess.Popen(
            [sys.executable, "-I", str(_HERE / "_proc_drain.py"), str(db), str(leases), str(log)],
        )
        for _ in range(10)
    ]
    assert [p.wait(timeout=120) for p in procs] == [0] * 10
    ran = Counter(log.read_text().split())
    assert {k: n for k, n in ran.items() if n > 1} == {}  # none run twice
    assert sorted(ran) == keys  # none lost
    p = work.progress()
    assert (p.done, p.by_status[Status.PENDING]) == (200, 0)
    work.close()
