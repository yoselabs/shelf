"""Run a child once, streaming its output, and always leave nothing of it running."""

from __future__ import annotations

import contextlib
import errno
import os
import select
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from stream_proc import proctable
from stream_proc.hold import popen_held
from stream_proc.registered import popen_registered
from stream_proc.tree import stop_tree

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from typing import IO

    from stream_proc.owned import OwnedProcess

Kind = Literal["wall", "idle", "stopped"]
_FIRST_NAP_S = 0.001  # the wait for a child starts short and doubles to _NAP_S: a child that ends in a few ms is seen in a few ms
_NAP_S = 0.02
MAX_LINE = 1 << 20  # default cap of one emitted piece and of the pending bytes of an unfinished line (1 MiB)


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


def _emit(cb: Callable[[bytes], None] | None, raw: bytes) -> None:
    if cb is not None:
        with contextlib.suppress(Exception):
            cb(raw)


def _text(cb: Callable[[str], None] | None) -> Callable[[bytes], None] | None:
    return None if cb is None else lambda raw: cb(raw.decode("utf-8", "replace"))


def _pump(
    stream: IO[bytes] | None,
    cb: Callable[[bytes], None] | None,
    touch: Callable[[], None],
    quit_: threading.Event,
    *,
    max_line: int = MAX_LINE,
    splits: list[int] | None = None,
) -> None:
    """Read lines until EOF (a torn last line included) so a full pipe never blocks; a failing callback never stops it.

    A line is held at most ``max_line`` bytes: when more arrives before its newline, the callback gets pieces of
    exactly ``max_line`` bytes (no newline) and ``splits[0]`` counts them, so a child that never prints a newline
    cannot grow memory. Polls the descriptor so ``quit_`` ends the reader even when a grandchild keeps the pipe
    open: the caller can then close the pipe without a reader inside it.
    """
    if stream is None:
        return
    fd = stream.fileno()
    buf = b""

    def emit_capped(data: bytes) -> bytes:
        while len(data) >= max_line:
            _emit(cb, data[:max_line])
            data = data[max_line:]
            if splits is not None:
                splits[0] += 1
        return data

    while not quit_.is_set():
        if not select.select([fd], [], [], 0.05)[0]:
            continue
        try:
            chunk = os.read(fd, min(65536, max_line))
        except OSError:
            break
        if not chunk:
            break
        touch()
        buf += chunk
        *lines, buf = buf.split(b"\n")
        for line in lines:
            rest = emit_capped(line + b"\n")
            if rest:
                _emit(cb, rest)
        buf = emit_capped(buf)
    if buf:
        _emit(cb, buf)


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
) -> Result:
    """Run ``argv`` in a session of its own and stream each output line (newline kept) to the callbacks.

    ``timeout`` is the wall limit, ``idle`` the longest silence on both streams, ``stop`` a flag checked while
    the child runs. A limit or the flag stops the whole tree (``stop_tree``: SIGTERM, ``grace``, SIGKILL, proof
    for ``prove`` seconds). If anything unwinds the wait (KeyboardInterrupt, a SIGTERM handler that raises, even
    one landing during the spawn) the tree is stopped first and the exception goes on. ``env`` is used as given
    (None inherits); stdin is /dev/null. ``drain`` bounds the wait for the last output after the child exited.
    ``max_line`` (>= 1, default 1 MiB) caps the bytes held for one line: a longer line reaches the callback in
    pieces of ``max_line`` bytes and ``Result.split_lines`` counts the cuts.
    """
    _check_max_line(max_line)
    t0 = time.monotonic()
    p, hold = popen_held(
        list(argv),
        cwd=cwd,
        env=None if env is None else dict(env),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    limits = _Limits(timeout, idle, stop, grace, prove, drain, max_line)
    return _supervise(p, ((p.stdout, _text(on_stdout)), (p.stderr, _text(on_stderr))), t0=t0, replay=hold.replay, limits=limits)


def run_registered(
    argv: Sequence[str],
    *,
    registered: Callable[[OwnedProcess], None],
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
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
    _check_max_line(max_line)
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
    return _supervise(p, ((p.stdout, on_line),), t0=t0, replay=lambda: None, limits=limits)


@dataclass(frozen=True, slots=True)
class _Limits:
    timeout: float | None
    idle: float | None
    stop: threading.Event | None
    grace: float
    prove: float
    drain: float
    max_line: int = MAX_LINE


def _check_max_line(max_line: int) -> None:
    if max_line < 1:
        message = f"max_line must be >= 1, got {max_line}"
        raise ValueError(message)


def _supervise(
    p: subprocess.Popen[bytes],
    pumps: tuple[tuple[IO[bytes] | None, Callable[[bytes], None] | None], ...],
    *,
    t0: float,
    replay: Callable[[], None],
    limits: _Limits,
) -> Result:
    """Pump ``pumps`` until the child ends or a limit stops its tree; on any unwinding the tree is stopped first."""
    last = [t0]
    readers: list[threading.Thread] = []
    splits: list[list[int]] = []
    quit_ = threading.Event()
    kind: Kind | None = None
    survivors: tuple[int, ...] = ()
    try:
        try:
            replay()
            for stream, cb in pumps:
                touch = lambda: last.__setitem__(0, time.monotonic())  # noqa: E731
                cuts = [0]
                splits.append(cuts)
                reader = threading.Thread(
                    target=_pump, args=(stream, cb, touch, quit_), kwargs={"max_line": limits.max_line, "splits": cuts}, daemon=True
                )
                reader.start()
                readers.append(reader)
            start = proctable.proc_start(p.pid)
            kind = _wait(p, t0=t0, last=last, timeout=limits.timeout, idle=limits.idle, stop=limits.stop)
            if kind is not None:
                survivors = stop_tree(p, grace=limits.grace, prove=limits.prove)
        except BaseException:
            stop_tree(p, grace=limits.grace, prove=limits.prove)
            raise
        end = time.monotonic() + (limits.drain if kind is None else 2.0)
        for reader in readers:
            reader.join(max(0.0, end - time.monotonic()))
    finally:
        _release(p, readers, quit_)
    code = p.returncode
    sig = -code if code is not None and code < 0 else None
    return Result(
        None if sig else code, sig, kind, p.pid, p.pid, start, time.monotonic() - t0, survivors, split_lines=sum(c[0] for c in splits)
    )


def _release(p: subprocess.Popen[bytes], readers: list[threading.Thread], quit_: threading.Event) -> None:
    """End every reader, then close the child's pipes: on every exit path nothing of the child stays open."""
    quit_.set()
    for reader in readers:
        reader.join(2.0)
    if any(reader.is_alive() for reader in readers):
        return  # a callback is stuck: closing a pipe under its reader is worse than the warning
    for stream in (p.stdout, p.stderr, p.stdin):
        if stream is not None:
            with contextlib.suppress(OSError):
                stream.close()
