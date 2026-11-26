"""Run a child once, streaming its output, and always leave nothing of it running."""

from __future__ import annotations

import contextlib
import errno
import subprocess
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from stream_proc import proctable
from stream_proc.hold import popen_held
from stream_proc.pump import MAX_LINE, Pump, check_max_line
from stream_proc.registered import popen_registered
from stream_proc.tree import stop_tree

if TYPE_CHECKING:
    import os
    import threading
    from collections.abc import Callable, Mapping, Sequence

    from stream_proc.owned import OwnedProcess

Kind = Literal["wall", "idle", "stopped"]
_FIRST_NAP_S = 0.001  # the wait for a child starts short and doubles to _NAP_S: a child that ends in a few ms is seen in a few ms
_NAP_S = 0.02


@dataclass(frozen=True, slots=True)
class Result:
    """How a run ended.

    ``returncode`` is the exit code, None when a signal ended the child (then ``signal`` is its number).
    ``timed_out`` is why *we* stopped it (``wall``, ``idle``, ``stopped``), None when it ended by itself.
    ``pid``, ``pgid`` (the child's own group) and ``start`` (its start token, None without ``/proc``) name it
    for good: a pid alone can be reused. ``survivors`` are pids of its tree still alive after the stop.
    ``exec_errno`` (:func:`run_registered` only) is the errno of an exec that failed after registration: the
    command never ran, ``returncode`` and ``signal`` are None. ``split_lines`` counts the times a line (or its
    unfinished part) reached ``max_line`` bytes and was emitted in pieces without a newline: 0 means every
    callback got whole lines.
    """

    returncode: int | None
    signal: int | None
    timed_out: Kind | None
    pid: int
    pgid: int
    start: str | None
    secs: float
    survivors: tuple[int, ...] = ()
    exec_errno: int | None = None
    split_lines: int = 0


def _text(cb: Callable[[str], None] | None) -> Callable[[bytes], None] | None:
    # lossy-ok: input: child output returned as text; a line callback wants text; the exact bytes are `capture`
    return None if cb is None else lambda raw: cb(raw.decode("utf-8", "replace"))


def _wait(
    p: subprocess.Popen[bytes],
    *,
    t0: float,
    last: list[float],
    timeout: float | None,
    idle: float | None,
    stop: threading.Event | None,
) -> Kind | None:
    nap = _FIRST_NAP_S
    while p.poll() is None:
        now = time.monotonic()
        if stop is not None and stop.is_set():
            return "stopped"
        if timeout is not None and now - t0 >= timeout:
            return "wall"
        if idle is not None and now - last[0] >= idle:
            return "idle"
        if stop is not None:
            stop.wait(nap)
        else:
            # returns the moment the child exits: a fixed 20 ms sleep made every short child cost 20 ms of wall
            with contextlib.suppress(subprocess.TimeoutExpired):
                p.wait(nap)
        nap = min(nap * 2, _NAP_S)
    return None


def run(
    argv: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    on_stdout: Callable[[str], None] | None = None,
    on_stderr: Callable[[str], None] | None = None,
    timeout: float | None = None,
    idle: float | None = None,
    stop: threading.Event | None = None,
    grace: float = 5.0,
    prove: float = 2.0,
    drain: float = 5.0,
    max_line: int = MAX_LINE,
    pass_fds: Sequence[int] = (),
) -> Result:
    """Run ``argv`` in a session of its own and stream each output line (newline kept) to the callbacks.

    ``pass_fds`` are descriptors the child inherits (everything else is closed), e.g. the terminal a step writes a notice to.

    ``timeout`` is the wall limit, ``idle`` the longest silence on both streams, ``stop`` a flag checked while
    the child runs. A limit or the flag stops the whole tree (``stop_tree``: SIGTERM, ``grace``, SIGKILL, proof
    for ``prove`` seconds). If anything unwinds the wait (KeyboardInterrupt, a SIGTERM handler that raises, even
    one landing during the spawn) the tree is stopped first and the exception goes on. ``env`` is used as given
    (None inherits); stdin is /dev/null. ``drain`` bounds the wait for the last output after the child exited.
    ``max_line`` (>= 1, default 1 MiB) caps the bytes held for one line: a longer line reaches the callback in
    pieces of ``max_line`` bytes and ``Result.split_lines`` counts the cuts.
    """
    check_max_line(max_line)
    t0 = time.monotonic()
    p, hold = popen_held(
        list(argv),
        cwd=cwd,
        env=None if env is None else dict(env),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        pass_fds=tuple(pass_fds),
    )
    limits = _Limits(timeout, idle, stop, grace, prove, drain, max_line)
    return _supervise(p, (_text(on_stdout), _text(on_stderr)), t0=t0, replay=hold.replay, limits=limits)


def run_registered(
    argv: Sequence[str],
    *,
    registered: Callable[[OwnedProcess], None],
    env: Mapping[str, str],
    cwd: str | os.PathLike[str] | None = None,
    timeout: float | None = None,
    on_line: Callable[[bytes], None] | None = None,
    stop: threading.Event | None = None,
    registration_timeout: float = 5.0,
    grace: float = 5.0,
    prove: float = 2.0,
    drain: float = 5.0,
    max_line: int = MAX_LINE,
) -> Result:
    """:func:`popen_registered`'s gate, then :func:`run`'s supervision: ``argv`` executes only after ``registered``
    returned with its identity, so a durable record names the process before any of its code runs.

    stdin is /dev/null; stderr is merged into stdout and each line (newline kept, exact bytes) goes to ``on_line``
    in the order written. ``timeout`` (wall, counted from this call, registration included) and ``stop`` stop
    and prove the whole tree as in :func:`run`. An exec failure after registration (ENOENT, EACCES) returns a
    Result with ``exec_errno`` set: the registered identity never ran the command, and its gate is reaped. Anything
    raised before the callback returned (a failing callback included) propagates with nothing executed;
    :class:`RegisteredStartUncertainError` propagates when the command may have started. On a normal exit, a
    descendant still in the group is left to the caller (``pgid`` names it, :func:`group_alive` observes it).
    ``max_line`` caps a held line as in :func:`run`.
    """
    check_max_line(max_line)
    t0 = time.monotonic()
    committed: list[OwnedProcess] = []

    def register(identity: OwnedProcess) -> None:
        registered(identity)
        committed.append(identity)

    try:
        p, _ = popen_registered(
            list(argv),
            registered=register,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            registration_timeout=registration_timeout,
        )
    except OSError as error:
        if not committed:
            raise
        who = committed[0]
        return Result(None, None, None, who.pid, who.pgid, who.start, time.monotonic() - t0, exec_errno=error.errno or errno.EIO)
    limits = _Limits(timeout, None, stop, grace, prove, drain, max_line)
    return _supervise(p, (on_line, None), t0=t0, replay=lambda: None, limits=limits)


@dataclass(frozen=True, slots=True)
class _Limits:
    timeout: float | None
    idle: float | None
    stop: threading.Event | None
    grace: float
    prove: float
    drain: float
    max_line: int = MAX_LINE


def _supervise(
    p: subprocess.Popen[bytes],
    streams: tuple[Callable[[bytes], None] | None, Callable[[bytes], None] | None],
    *,
    t0: float,
    replay: Callable[[], None],
    limits: _Limits,
) -> Result:
    """Pump the child's output until it ends or a limit stops its tree; on any unwinding the tree is stopped first."""
    last = [t0]
    pump = Pump(
        p,
        on_stdout=streams[0],
        on_stderr=streams[1],
        touch=lambda: last.__setitem__(0, time.monotonic()),
        max_line=limits.max_line,
    )
    kind: Kind | None = None
    survivors: tuple[int, ...] = ()
    try:
        try:
            replay()
            pump.start()
            start = proctable.proc_start(p.pid)
            kind = _wait(p, t0=t0, last=last, timeout=limits.timeout, idle=limits.idle, stop=limits.stop)
            if kind is not None:
                survivors = stop_tree(p, grace=limits.grace, prove=limits.prove)
        except BaseException:
            stop_tree(p, grace=limits.grace, prove=limits.prove)
            raise
        pump.drain(limits.drain if kind is None else 2.0)
    finally:
        pump.release()
    code = p.returncode
    sig = -code if code is not None and code < 0 else None
    return Result(None if sig else code, sig, kind, p.pid, p.pid, start, time.monotonic() - t0, survivors, split_lines=pump.splits)
