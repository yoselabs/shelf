"""Run a child to its end and hand back its whole output as one :class:`Captured`: exact bytes, with text as a view."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING, Any

from stream_proc.hold import popen_held
from stream_proc.pump import Pump
from stream_proc.runner import _wait
from stream_proc.tree import stop_tree

if TYPE_CHECKING:
    import os
    from collections.abc import Mapping, Sequence

TIMEOUT_EXIT = 124  # the exit code of coreutils ``timeout``


@dataclass(frozen=True, slots=True)
class Captured:
    """What :func:`capture` saw: ``exit`` (124 on a timeout, ``-signal`` when a signal ended the child), ``out`` and
    ``err`` as the exact bytes in full (on a timeout, what the child wrote before it was stopped), ``secs`` wall time,
    ``timed_out``, and ``survivors`` (pids left after the stop) and ``peak_rss`` (bytes: the child's own high-water
    resident set, the largest of it and the descendants it waited for; None when the child was reaped by someone else;
    a lower bound for a tree, see ``MeasuredPopen``).

    Store or forward ``out``/``err``; show ``text``/``err_text``, the same bytes as UTF-8 with undecodable bytes replaced
    by U+FFFD and newlines kept as written."""

    exit: int
    out: bytes
    err: bytes
    secs: float
    timed_out: bool
    survivors: tuple[int, ...] = ()
    peak_rss: int | None = None

    @property
    def text(self) -> str:
        """``out`` for a person to read: UTF-8, bad bytes replaced."""
        # lossy-ok: display: the one decode of child output; callers that store or forward it use the bytes
        return self.out.decode("utf-8", "replace")

    @property
    def err_text(self) -> str:
        """``err`` for a person to read: UTF-8, bad bytes replaced."""
        # lossy-ok: display: the one decode of child output; callers that store or forward it use the bytes
        return self.err.decode("utf-8", "replace")


def capture(
    argv: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float,
    input: bytes | None = None,  # noqa: A002 - subprocess.run's name
    stdin: int | IO[Any] | None = subprocess.DEVNULL,  # Any: passed through to subprocess unchanged
    grace: float = 5.0,
    drain: float = 2.0,
) -> Captured:
    """Run ``argv`` in a session of its own to its end; stdout and stderr come back as exact bytes (no decoding, no newline conversion).

    ``stdin`` is a ``subprocess`` value: ``subprocess.DEVNULL`` (default), ``None`` (inherit ours), a descriptor or a
    file. ``input`` feeds bytes instead (a pipe, written while the output is read, so large input and large output never
    deadlock; a child that exits without reading it all is not an error); give ``input`` or ``stdin``, not both
    (``ValueError``). The child is always
    a session leader, so even with an inherited stdin it has no controlling terminal (no tty job control, no ``/dev/tty``).

    The wait is on the child, not on its pipes: ``timeout`` is the wall limit for the child; hitting it stops the whole
    tree (``grace``) and returns exit 124 with ``timed_out`` set, not an exception, with the partial
    output in ``out``/``err``. After the child ended (or was stopped) the pipes are read for at most ``drain`` more seconds,
    so a process that outlived the child and still holds a pipe (``sleep 30 &``) delays the result by ``drain``, never by
    its own lifetime; whatever arrived by then is returned. An exception that unwinds the wait (KeyboardInterrupt, a raising
    SIGTERM handler, even one landing during the spawn) stops the tree first and goes on. The output is not capped.
    """
    return _run(argv, cwd=cwd, env=env, timeout=timeout, input=input, stdin=stdin, grace=grace, drain=drain, pipe=subprocess.PIPE)


def run_inherited(
    argv: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float,
    stdin: int | IO[Any] | None = subprocess.DEVNULL,  # Any: passed through to subprocess unchanged
    grace: float = 5.0,
) -> int:
    """:func:`capture` for a child that writes to OUR stdout and stderr (a build someone watches): returns its exit code.

    The exit is 124 on a timeout (the tree is stopped, as in :func:`capture`) and ``-signal`` when a signal ended
    the child. The child shares our descriptors but, as always, is a session leader with no controlling terminal.
    """
    return _run(argv, cwd=cwd, env=env, timeout=timeout, input=None, stdin=stdin, grace=grace, drain=0.0, pipe=None).exit


def _run(
    argv: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None,
    env: Mapping[str, str] | None,
    timeout: float,
    input: bytes | None,  # noqa: A002 - subprocess.run's name
    stdin: int | IO[Any] | None,
    grace: float,
    drain: float,
    pipe: int | None,
) -> Captured:
    if input is not None and stdin != subprocess.DEVNULL:
        msg = "give input or stdin, not both"
        raise ValueError(msg)
    t0 = time.monotonic()
    p, hold = popen_held(
        list(argv),
        cwd=cwd,
        env=None if env is None else dict(env),
        stdin=subprocess.PIPE if input is not None else stdin,
        stdout=pipe,
        stderr=pipe,
        start_new_session=True,
    )
    out: list[bytes] = []
    err: list[bytes] = []
    pump = Pump(p, on_stdout=out.append, on_stderr=err.append, stdin=input)
    survivors: tuple[int, ...] = ()
    timed = False
    try:
        try:
            hold.replay()
            pump.start()
            timed = _wait(p, t0=t0, last=[t0], timeout=timeout, idle=None, stop=None) is not None
            if timed:
                survivors = stop_tree(p, grace=grace)
        except BaseException:
            stop_tree(p, grace=grace)
            raise
        pump.drain(drain)
    finally:
        pump.release()
    code = p.returncode
    exit_ = TIMEOUT_EXIT if timed else (code if code is not None else -1)
    return Captured(exit_, b"".join(out), b"".join(err), time.monotonic() - t0, timed, survivors, p.peak_rss)
