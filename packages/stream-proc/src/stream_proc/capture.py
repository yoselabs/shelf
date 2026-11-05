"""Run a child to its end and hand back its whole output: as text (:func:`capture`) or as exact bytes (:func:`capture_bytes`)."""

from __future__ import annotations

import contextlib
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from stream_proc.hold import popen_held
from stream_proc.runner import run
from stream_proc.tree import stop_tree

if TYPE_CHECKING:
    import os
    from collections.abc import Callable, Mapping, Sequence

TIMEOUT_EXIT = 124  # the exit code of coreutils ``timeout``


@dataclass(frozen=True, slots=True)
class Captured:
    """What :func:`capture` saw: ``exit`` (124 on a timeout, ``-signal`` when a signal ended the child), the decoded
    ``out`` and ``err`` in full, ``secs`` wall time, ``timed_out``, and ``survivors`` (pids left after the stop)."""

    exit: int
    out: str
    err: str
    secs: float
    timed_out: bool
    survivors: tuple[int, ...] = ()


def capture(
    argv: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    tick: Callable[[], None] | None = None,
    poll_s: float = 0.2,
    grace: float = 5.0,
) -> Captured:
    """:func:`run` to the end, stdout and stderr collected as text (UTF-8, bad bytes replaced, newlines kept as written).

    ``timeout`` is the wall limit; hitting it stops the whole tree and reports exit 124. ``tick`` runs every ``poll_s``
    seconds on a helper thread while the child lives, and once more after it ends (a heartbeat;
    an exception from it is ignored). An exception that
    unwinds the wait stops the tree first, as in :func:`run`. The output is not capped: it all sits in memory.
    """
    out: list[str] = []
    err: list[str] = []
    done = threading.Event()
    helper = None
    if tick is not None:
        beat = tick

        def ticker() -> None:
            while not done.wait(poll_s):
                with contextlib.suppress(Exception):
                    beat()

        helper = threading.Thread(target=ticker, daemon=True)
        helper.start()
    try:
        res = run(argv, cwd=cwd, env=env, on_stdout=out.append, on_stderr=err.append, timeout=timeout, grace=grace)
    finally:
        done.set()
        if helper is not None:
            helper.join(2)
    if tick is not None:
        with contextlib.suppress(Exception):
            tick()  # a failing heartbeat never costs the result
    timed = res.timed_out is not None
    code = TIMEOUT_EXIT if timed else (res.returncode if res.returncode is not None else -(res.signal or 1))
    return Captured(code, "".join(out), "".join(err), res.secs, timed, res.survivors)


@dataclass(frozen=True, slots=True)
class CapturedBytes:
    """What :func:`capture_bytes` saw: like :class:`Captured`, but ``out`` and ``err`` are the exact bytes (b"" when
    ``capture=False``). On a timeout they hold what the child wrote before it was stopped."""

    exit: int
    out: bytes
    err: bytes
    secs: float
    timed_out: bool
    survivors: tuple[int, ...] = ()


def capture_bytes(
    argv: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    input: bytes | None = None,  # noqa: A002 - subprocess.run's name
    stdin: Literal["devnull", "inherit"] = "devnull",
    capture: bool = True,
    grace: float = 5.0,
    drain: float = 2.0,
) -> CapturedBytes:
    """Run ``argv`` in a session of its own to its end; stdout and stderr come back as exact bytes (no decoding, no newline conversion).

    ``input`` is fed to stdin (written while the output is read, so a large input and a large output never deadlock)
    and then closed; without it stdin is /dev/null (``stdin="devnull"``) or ours (``"inherit"``). ``capture=False``
    leaves stdout and stderr inherited and returns them empty. Like :func:`capture`, hitting ``timeout`` stops the
    whole tree (``grace``) and returns exit 124 with ``timed_out`` set, not an exception; ``out``/``err`` then carry the
    partial output. The final read is bounded to ``drain`` seconds, since an unrelated process may hold a pipe open.
    An exception that unwinds the wait (KeyboardInterrupt, a raising SIGTERM handler, even one landing during the
    spawn) stops the tree first and goes on. The output is not capped.
    """
    t0 = time.monotonic()
    pipe = subprocess.PIPE if capture else None
    p, hold = popen_held(
        list(argv),
        cwd=cwd,
        env=None if env is None else dict(env),
        stdin=subprocess.PIPE if input is not None else (None if stdin == "inherit" else subprocess.DEVNULL),
        stdout=pipe,
        stderr=pipe,
        start_new_session=True,
    )
    out: bytes | None
    err: bytes | None
    survivors: tuple[int, ...] = ()
    timed = False
    try:
        try:
            hold.replay()
            out, err = p.communicate(input=input, timeout=timeout)
        except subprocess.TimeoutExpired as expired:
            timed = True
            survivors = stop_tree(p, grace=grace)
            out, err = expired.output, expired.stderr
            try:
                out, err = p.communicate(timeout=drain)
            except subprocess.TimeoutExpired as late:
                out = late.output if late.output is not None else out
                err = late.stderr if late.stderr is not None else err
        except BaseException:
            stop_tree(p, grace=grace)
            raise
    finally:
        for stream in (p.stdin, p.stdout, p.stderr):
            if stream is not None:
                with contextlib.suppress(OSError):
                    stream.close()
    code = p.returncode
    exit_ = TIMEOUT_EXIT if timed else (code if code is not None else -1)
    return CapturedBytes(exit_, out or b"", err or b"", time.monotonic() - t0, timed, survivors)
