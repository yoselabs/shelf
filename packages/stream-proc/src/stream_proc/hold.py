"""A SIGTERM or SIGINT (Ctrl-C) that arrives while a child is being spawned must still stop that child.

Python runs a signal handler between bytecodes of the main thread. A handler that raises (SIGINT's
default one raises KeyboardInterrupt), running inside ``Popen()`` or before the caller's ``try``,
makes the spawn raise: the caller never stops the new child, and it (and its tree) runs on, owned by
nobody. ``TermHold`` swaps each handler for one that only notes the signal while the child is being
spawned; ``replay`` puts the real handlers back and runs the noted ones, at a point where the caller
can already stop the child.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
from typing import TYPE_CHECKING, Any, Literal, Self, override

if TYPE_CHECKING:
    import resource
    from types import FrameType, TracebackType

HELD = (signal.SIGTERM, signal.SIGINT)


class TermHold:
    """``with TermHold() as hold: p = Popen(...)``, then ``hold.replay()`` first thing inside the ``try`` that stops ``p``.

    Holds SIGTERM and SIGINT. A no-op off the main thread (signal handlers live there only) and for a
    signal with no Python handler (the default action then ends the process, as it should).
    """

    def __init__(self) -> None:
        self.old: dict[int, Any] = {}
        self.held: list[int] = []

    def __enter__(self) -> Self:
        self.old = {}
        self.held = []
        if threading.current_thread() is threading.main_thread():
            for signum in HELD:
                old = signal.getsignal(signum)
                if callable(old):
                    self.old[signum] = old
                    signal.signal(signum, self._note)
        return self

    def __exit__(self, kind: type[BaseException] | None, value: BaseException | None, tb: TracebackType | None) -> Literal[False]:
        if kind is not None:  # a failed spawn has nothing to stop: run a held handler now, never lose the signal
            self.replay()
        return False

    def _note(self, signum: int, _frame: FrameType | None) -> None:
        if signum not in self.held:
            self.held.append(signum)

    def release(self) -> None:
        for signum, old in self.old.items():
            signal.signal(signum, old)

    def replay(self) -> None:
        """Put the real handlers back; run the handler of each held signal, in arrival order."""
        self.release()
        held = self.held
        self.held = []
        for signum in held:
            self.old[signum](signum, None)


_RSS_UNIT = 1 if sys.platform == "darwin" else 1024  # ru_maxrss is bytes on macOS, kilobytes on Linux


def peak_bytes(usage: resource.struct_rusage) -> int:
    """The high-water resident set in a ``wait4`` rusage, in bytes: the one place the OS's ``ru_maxrss`` unit is known."""
    return usage.ru_maxrss * _RSS_UNIT


class MeasuredPopen(subprocess.Popen[bytes]):
    """A ``Popen`` whose reaping is ``os.wait4``, so the kernel's resource usage of exactly this child is kept.

    ``peak_rss`` (bytes) is the child's high-water resident set, the largest of it and of the descendants it
    waited for itself; None until the child is reaped here. It is per child (``RUSAGE_CHILDREN`` would be the largest
    of every child this process ever waited for). A descendant that was never waited for by its parent
    (killed with the tree, or orphaned to init) is not in it, so for a tree it is a lower bound. Overrides
    ``Popen._try_wait`` (its signature is the same on CPython 3.12 to 3.15) and routes the public ``poll`` through
    ``wait``. ``Popen._internal_poll`` is not overridden: its private ``_waitpid`` argument is gone in 3.15, and only
    ``__del__`` still reaps through it (an unwaited child, which nobody measures).
    """

    peak_rss: int | None = None

    def _reap(self, pid: int, flags: int) -> tuple[int, int]:
        pid, status, usage = os.wait4(pid, flags)
        if pid == self.pid:
            self.peak_rss = peak_bytes(usage)
        return pid, status

    def _try_wait(self, wait_flags: int) -> tuple[int, int]:
        try:
            return self._reap(self.pid, wait_flags)
        except ChildProcessError:
            return self.pid, 0  # CPython's own answer when something else reaped it: dead, no status

    @override
    def poll(self) -> int | None:
        """Public ``poll`` as a zero-timeout ``wait``, so it reaps through ``_try_wait`` and keeps the measurement."""
        if self.returncode is None:
            with contextlib.suppress(subprocess.TimeoutExpired):
                self.wait(timeout=0)
        return self.returncode


def popen_held(*args: Any, **kwargs: Any) -> tuple[MeasuredPopen, TermHold]:  # Any: passed through to subprocess.Popen unchanged
    """``(MeasuredPopen(*args, **kwargs), hold)``; the caller calls ``hold.replay()`` inside the ``try`` that stops the child."""
    with TermHold() as hold:
        return MeasuredPopen(*args, **kwargs), hold
