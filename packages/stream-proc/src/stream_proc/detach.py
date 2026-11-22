"""Start a child that outlives its caller: own session, stdin /dev/null, output appended to a log file."""

from __future__ import annotations

import dataclasses
import subprocess
from typing import TYPE_CHECKING

from stream_proc import proctable
from stream_proc.owned import IdentityUnavailableError
from stream_proc.tree import stop_tree

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path


@dataclasses.dataclass(frozen=True, slots=True)
class Detached:
    """The identity of a detached child: store ``(pid, start)``, never the pid alone."""

    pid: int
    start: str


def spawn_detached(argv: Sequence[str], *, cwd: Path, env: Mapping[str, str], log: Path) -> Detached:
    """Start ``argv`` in a session of its own and return at once; the caller's pipes are never inherited.

    stdin is /dev/null, stdout and stderr are appended to ``log`` (its folder is created), every other descriptor is closed,
    so a caller reading our stdout or stderr sees EOF when we exit, not when the child does. ``env`` is exactly the child's
    environment. A spawn failure (``FileNotFoundError``, ``PermissionError``) raises natively. When the identity cannot be
    read (no process table, or the child is already gone) the child is stopped and :class:`IdentityUnavailableError` raised:
    a worker nobody can recognise later is never left running.
    """
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as out:
        p = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    start = proctable.proc_start(p.pid)
    if start is None:
        stop_tree(p)
        msg = f"cannot read the start identity of pid {p.pid} ({argv[0]}): no process table, or it exited at once"
        raise IdentityUnavailableError(msg)
    return Detached(p.pid, start)
