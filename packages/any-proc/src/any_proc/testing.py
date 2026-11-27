"""Test children that must not outlive the test process.

A test that starts a server or a worker leaves it running when the test process dies without a finalizer
(SIGKILL, a crashed xdist worker, a closed terminal); orphaned servers outlived runs for days (a2kay-71ou).
:func:`start_child` starts the child as the leader of a process group of its own (so its own children die with it)
and a detached watcher that kills that group once the test process is gone. :func:`kill_group` is the orderly stop;
an ``atexit`` finalizer stops every child still live. Stdlib plus ``stream-proc``, POSIX.
"""

from __future__ import annotations

import atexit
import contextlib
import os
import subprocess
import sys
from typing import Any

from stream_proc import stop_tree

__all__ = ["Child", "kill_group", "start_child"]

# Runs in the watcher: while its parent (the test process) lives it only checks the group is still there;
# once the parent is gone it SIGTERMs the group, then SIGKILLs it.
_WATCHER = """
import os, signal, sys, time
owner, group = int(sys.argv[1]), int(sys.argv[2])
while os.getppid() == owner:
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        sys.exit(0)
    time.sleep(0.2)
for sig in (signal.SIGTERM, signal.SIGKILL):
    try:
        os.killpg(group, sig)
    except ProcessLookupError:
        sys.exit(0)
    time.sleep(2)
"""

Child = subprocess.Popen[Any]

_live: list[Child] = []
# Each child's watcher, held so the Popen is not collected while it still runs (a collected live Popen is a ResourceWarning,
# an error under `filterwarnings = ["error"]`); `kill_group` reaps it once the group is gone and the watcher exits on its own.
_watchers: dict[int, subprocess.Popen[Any]] = {}


def start_child(argv: list[str], **popen_kwargs: Any) -> Child:  # Any: Popen's own keyword arguments, passed through
    """``subprocess.Popen(argv, **popen_kwargs)`` as the leader of a new process group, watched until the test process dies."""
    child = subprocess.Popen(argv, start_new_session=True, **popen_kwargs)
    _watchers[child.pid] = subprocess.Popen(
        [sys.executable, "-c", _WATCHER, str(os.getpid()), str(child.pid)],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _live.append(child)
    return child


def kill_group(child: Child, *, grace: float = 10.0) -> None:
    """Stop ``child`` and everything it started: SIGTERM to the group, SIGKILL after ``grace``; closes its pipes and reaps its watcher."""
    stop_tree(child, grace=grace)
    for pipe in (child.stdin, child.stdout, child.stderr):
        if pipe is not None:
            pipe.close()
    if child in _live:
        _live.remove(child)
    if (watcher := _watchers.pop(child.pid, None)) is not None:
        with contextlib.suppress(subprocess.TimeoutExpired):
            watcher.wait(5)


def _reap_all() -> None:
    while _live:  # kill_group takes each child out of the list
        kill_group(_live[0], grace=2.0)


atexit.register(_reap_all)
