"""Stop a child's whole tree and prove it dead.

The child leads a session of its own, so its process group is its tree, except for descendants that
called ``setsid`` or ``setpgid`` and left it. Those are noted from the process table *before* the stop
(afterwards init adopts them and the link is gone) and signalled by pid, only while pid and start
token still match, so a reused pid is never hit.

The order: SIGTERM to the group and to each noted descendant, a grace period, SIGKILL to what
is left, then a proof loop that re-reads the table and kills again until nothing of the tree lives or
the proof time is out. Survivors are returned, never hidden. Nothing here runs ``ps`` or any tool.
Where there is no process table (``/proc`` or libproc unreadable) only the group is signalled and the proof is "the group is empty".
"""

from __future__ import annotations

import contextlib
import dataclasses
import os
import signal
import subprocess
import time
from typing import TYPE_CHECKING

from stream_proc import proctable

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclasses.dataclass(frozen=True)
class StopReport:
    """What :func:`stop_tree_report` did, as facts of the signal calls themselves, never inferred from time or survivors.

    ``term_sent`` / ``kill_sent``: at least one SIGTERM / SIGKILL call was made (False when the stop failed before any call, or the
    only targets were ones that are never signalled). ``term_delivered`` / ``kill_delivered``: at least one such call returned
    without error (ESRCH and EPERM leave it False). ``error``: the stop itself raised; the flags hold what happened before, and
    ``survivors`` is then unknown (empty).
    """

    survivors: tuple[int, ...] = ()
    term_sent: bool = False
    term_delivered: bool = False
    kill_sent: bool = False
    kill_delivered: bool = False
    error: bool = False


class _Sent:
    """Mutable tally behind a :class:`StopReport`: every signal call goes through :meth:`call`."""

    def __init__(self) -> None:
        self.tried: set[int] = set()
        self.ok: set[int] = set()

    def call(self, sig: int, fn: Callable[[int, int], None], target: int) -> bool:
        self.tried.add(sig)
        try:
            fn(target, sig)
        except OSError:
            return False
        self.ok.add(sig)
        return True

    def report(self, survivors: tuple[int, ...], *, error: bool = False) -> StopReport:
        t, k = signal.SIGTERM, signal.SIGKILL
        return StopReport(survivors, t in self.tried, t in self.ok, k in self.tried, k in self.ok, error)


def own_ids() -> set[int]:
    """Pids and group ids this process must never signal: itself, its group, its parent and the parent's group."""
    ids = {os.getpid(), os.getpgrp(), os.getppid()}
    with contextlib.suppress(OSError):
        ids.add(os.getpgid(os.getppid()))
    return ids


def _hit(pid: int, sig: int, sent: _Sent, *, group: bool = True) -> None:
    """Signal ``pid`` and, when ``group``, its own group; never ours, never pid or group 0 or 1."""
    if pid <= 1 or pid in own_ids():
        return
    with contextlib.suppress(OSError):
        pgid = os.getpgid(pid)
        if group and pgid > 1 and pgid not in own_ids():
            sent.call(sig, os.killpg, pgid)
    sent.call(sig, os.kill, pid)


def _leads(p: subprocess.Popen[bytes]) -> bool:
    """True when the child leads a group of its own. An unreaped child's pid is its group id, so it cannot have been reused."""
    try:
        return os.getpgid(p.pid) == p.pid
    except OSError:
        return p.returncode is not None and p.pid not in own_ids()


def _survivors(p: subprocess.Popen[bytes], *, led: bool, noted: dict[int, str]) -> list[int]:
    """Pids of the tree still alive: the noted ones with an unchanged start token, the group's members, and all below those."""
    ours = own_ids()
    if not proctable.has_table():
        return [p.pid] if led and proctable.group_alive(p.pid) else []
    rows = proctable.table()
    live = {pid for pid, start in noted.items() if proctable.alive(pid, start)}
    if p.returncode is None and proctable.alive(p.pid):
        live.add(p.pid)
    if led:
        live |= {r.pid for r in rows.values() if r.pgid == p.pid and not r.state.startswith(("Z", "X"))}
    for pid in list(live):
        live |= {r.pid for r in proctable.descendants(pid, rows) if not r.state.startswith(("Z", "X"))}
    return sorted(live - ours)


def stop_tree(p: subprocess.Popen[bytes], *, grace: float = 5.0, prove: float = 2.0) -> tuple[int, ...]:
    """Stop ``p`` and everything under it; returns the pids still alive after SIGKILL and ``prove`` seconds (normally empty).

    SIGTERM first so a child can clean up, SIGKILL after ``grace`` seconds. A child that does not lead
    its own group is signalled alone, never through a group that is ours.
    """
    return stop_tree_report(p, grace=grace, prove=prove).survivors


def stop_tree_report(p: subprocess.Popen[bytes], *, grace: float = 5.0, prove: float = 2.0) -> StopReport:
    """:func:`stop_tree` that also says which signals were attempted and which the kernel took: -> :class:`StopReport`."""
    sent = _Sent()
    try:
        survivors = _stop(p, grace, prove, sent)
    except Exception:  # noqa: BLE001 - the report says the stop failed and what went out before that, never hides it
        return sent.report((), error=True)
    return sent.report(survivors)


def _stop(p: subprocess.Popen[bytes], grace: float, prove: float, sent: _Sent) -> tuple[int, ...]:
    led = _leads(p)
    rows = proctable.table()
    noted = {r.pid: r.start for r in proctable.descendants(p.pid, rows)}
    # The child and its group first: a shell that `wait`s on a background job whose own SIGTERM arrives first sees the job end and exits 0
    # (macOS bash 3.2 does, on most runs), so a stopped tree would read as a success; with the group signalled at once the shell dies too.
    if led and p.pid not in own_ids():
        sent.call(signal.SIGTERM, os.kill, p.pid)  # the leader alone, then everyone: the group walk reaches a member before the leader
        sent.call(signal.SIGTERM, os.killpg, p.pid)
    elif p.returncode is None:
        _hit(p.pid, signal.SIGTERM, sent, group=False)
    for pid in noted:
        _hit(pid, signal.SIGTERM, sent)
    end = time.monotonic() + grace
    while time.monotonic() < end:
        p.poll()
        if p.returncode is not None and not _survivors(p, led=led, noted=noted):
            return ()
        time.sleep(0.02)
    end = time.monotonic() + prove
    while True:
        if led and p.returncode is None and p.pid not in own_ids():
            sent.call(signal.SIGKILL, os.killpg, p.pid)  # unreaped: the group id is still ours to name
        left = _survivors(p, led=led, noted=noted)
        for pid in left:
            _hit(pid, signal.SIGKILL, sent, group=pid != p.pid or led)
        p.poll()
        left = _survivors(p, led=led, noted=noted)
        if (not left and p.returncode is not None) or time.monotonic() >= end:
            break
        time.sleep(0.02)
    with contextlib.suppress(subprocess.TimeoutExpired):
        p.wait(timeout=1)
    return tuple(_survivors(p, led=led, noted=noted))
