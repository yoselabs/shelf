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

from stream_proc import proctable


@dataclasses.dataclass(frozen=True)
class StopReport:
    """What :func:`stop_tree_report` did: ``survivors`` (pids alive at the end), and per signal whether the kernel took it.

    ``term_delivered`` / ``kill_delivered`` are True when at least one SIGTERM / SIGKILL call returned without error (a signal
    that never went out, or only met ESRCH or EPERM, stays False); ``kill_sent`` is whether SIGKILL was attempted at all.
    """

    survivors: tuple[int, ...] = ()
    term_delivered: bool = False
    kill_sent: bool = False
    kill_delivered: bool = False


class _Sent:
    """Mutable tally behind a :class:`StopReport`."""

    def __init__(self) -> None:
        self.term = self.kill = self.kill_tried = False

    def note(self, sig: int, ok: bool) -> None:  # noqa: FBT001 - an internal tally
        if sig == signal.SIGTERM:
            self.term = self.term or ok
        else:
            self.kill_tried = True
            self.kill = self.kill or ok


def own_ids() -> set[int]:
    """Pids and group ids this process must never signal: itself, its group, its parent and the parent's group."""
    ids = {os.getpid(), os.getpgrp(), os.getppid()}
    with contextlib.suppress(OSError):
        ids.add(os.getpgid(os.getppid()))
    return ids


def _hit(pid: int, sig: int, *, group: bool = True) -> bool:
    """Signal ``pid`` and, when ``group``, its own group; never ours, never pid or group 0 or 1. -> True when a signal call succeeded."""
    if pid <= 1 or pid in own_ids():
        return False
    ok = False
    with contextlib.suppress(OSError):
        pgid = os.getpgid(pid)
        if group and pgid > 1 and pgid not in own_ids():
            os.killpg(pgid, sig)
            ok = True
    with contextlib.suppress(OSError):
        os.kill(pid, sig)
        ok = True
    return ok


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
    """:func:`stop_tree` that also says which signals the kernel took: -> :class:`StopReport`."""
    sent = _Sent()
    survivors = _stop(p, grace, prove, sent)
    return StopReport(survivors=survivors, term_delivered=sent.term, kill_sent=sent.kill_tried, kill_delivered=sent.kill)


def _stop(p: subprocess.Popen[bytes], grace: float, prove: float, sent: _Sent) -> tuple[int, ...]:
    led = _leads(p)
    rows = proctable.table()
    noted = {r.pid: r.start for r in proctable.descendants(p.pid, rows)}
    # The child and its group first: a shell that `wait`s on a background job whose own SIGTERM arrives first sees the job end and exits 0
    # (macOS bash 3.2 does, on most runs), so a stopped tree would read as a success; with the group signalled at once the shell dies too.
    if led and p.pid not in own_ids():
        with contextlib.suppress(OSError):
            os.kill(p.pid, signal.SIGTERM)  # the leader alone, then everyone: the group walk reaches a member before the leader
            sent.note(signal.SIGTERM, True)  # noqa: FBT003
            os.killpg(p.pid, signal.SIGTERM)
    elif p.returncode is None:
        sent.note(signal.SIGTERM, _hit(p.pid, signal.SIGTERM, group=False))
    for pid in noted:
        sent.note(signal.SIGTERM, _hit(pid, signal.SIGTERM))
    end = time.monotonic() + grace
    while time.monotonic() < end:
        p.poll()
        if p.returncode is not None and not _survivors(p, led=led, noted=noted):
            return ()
        time.sleep(0.02)
    end = time.monotonic() + prove
    while True:
        if led and p.returncode is None and p.pid not in own_ids():
            sent.kill_tried = True
            with contextlib.suppress(OSError):
                os.killpg(p.pid, signal.SIGKILL)  # unreaped: the group id is still ours to name
                sent.note(signal.SIGKILL, True)  # noqa: FBT003
        left = _survivors(p, led=led, noted=noted)
        for pid in left:
            sent.note(signal.SIGKILL, _hit(pid, signal.SIGKILL, group=pid != p.pid or led))
        p.poll()
        left = _survivors(p, led=led, noted=noted)
        if (not left and p.returncode is not None) or time.monotonic() >= end:
            break
        time.sleep(0.02)
    with contextlib.suppress(subprocess.TimeoutExpired):
        p.wait(timeout=1)
    return tuple(_survivors(p, led=led, noted=noted))
