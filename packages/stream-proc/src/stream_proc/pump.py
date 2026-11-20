"""The pump of a held child: line readers for stdout and stderr, a stdin feeder, and the lifetime of the three pipes."""

from __future__ import annotations

import contextlib
import os
import select
import threading
import time
from typing import IO, TYPE_CHECKING

if TYPE_CHECKING:
    import subprocess
    from collections.abc import Callable, Iterator

MAX_LINE = 1 << 20  # default cap of one emitted piece and of the pending bytes of an unfinished line (1 MiB)
_POLL_S = 0.05  # how often a reader or the feeder looks at the quit flag while its pipe is quiet
_CHUNK = 65536


def check_max_line(max_line: int) -> None:
    if max_line < 1:
        message = f"max_line must be >= 1, got {max_line}"
        raise ValueError(message)


class _Lines:
    """One reader: the lines (capped pieces) of one pipe to one callback, until EOF or the quit flag."""

    def __init__(
        self,
        stream: IO[bytes],
        cb: Callable[[bytes], None] | None,
        touch: Callable[[], None] | None,
        *,
        max_line: int,
        quit_: threading.Event,
        count_cut: Callable[[], None],
    ) -> None:
        self.stream, self.cb, self.touch, self.max_line, self.quit, self.count_cut = stream, cb, touch, max_line, quit_, count_cut

    def emit(self, raw: bytes) -> None:
        if self.cb is not None:
            with contextlib.suppress(Exception):
                self.cb(raw)

    def cut(self, data: bytes) -> bytes:
        while len(data) >= self.max_line:
            self.emit(data[: self.max_line])
            data = data[self.max_line :]
            self.count_cut()
        return data

    def chunks(self) -> Iterator[bytes]:
        fd = self.stream.fileno()
        while not self.quit.is_set():
            if not select.select([fd], [], [], _POLL_S)[0]:
                continue
            try:
                chunk = os.read(fd, min(_CHUNK, self.max_line))
            except OSError:
                return
            if not chunk:
                return
            if self.touch is not None:
                with contextlib.suppress(Exception):
                    self.touch()
            yield chunk

    def run(self) -> None:
        pending = b""
        for chunk in self.chunks():
            *lines, rest = (pending + chunk).split(b"\n")
            for line in lines:
                if tail := self.cut(line + b"\n"):
                    self.emit(tail)
            pending = self.cut(rest)
        if pending:
            self.emit(pending)


class Pump:
    """Reads a child's stdout and stderr as lines, feeds its stdin, and owns the pipes until :meth:`release`.

    ``p`` is a ``Popen`` whose pipes this pump now owns: nothing else reads, writes or closes them. Callbacks get
    ``bytes`` (newline kept, the torn last line too) and never stop the reading when they raise. A line is held at
    most ``max_line`` bytes: a longer one reaches the callback in pieces of exactly ``max_line`` bytes without a
    newline, ``splits`` counts the cuts, so a child that never prints a newline cannot grow memory. ``touch`` runs
    when bytes arrive. ``stdin`` is written as the child takes it and then closed (the end of input); a child that
    exits or stops reading ends the feed quietly. ``None`` writes nothing and leaves the pipe open until release.

    Lifetime, in order: :meth:`start` (once, after any replay), :meth:`drain` (wait for the end of the output),
    :meth:`release` (always, from the owner). Every reader polls its descriptor, so a grandchild that keeps a
    pipe open cannot pin one. Release asks them to quit, waits for every reader and the feeder to be out, and only
    then closes the pipes: no pipe is closed under a thread using it. A callback that never returns therefore
    holds release, by design: closing under it would be the race.
    """

    def __init__(
        self,
        p: subprocess.Popen[bytes],
        *,
        on_stdout: Callable[[bytes], None] | None = None,
        on_stderr: Callable[[bytes], None] | None = None,
        stdin: bytes | None = None,
        touch: Callable[[], None] | None = None,
        max_line: int = MAX_LINE,
    ) -> None:
        check_max_line(max_line)
        self._p = p
        self._quit = threading.Event()
        self._lock = threading.Lock()
        self._splits = 0
        self._threads: list[threading.Thread] = []
        self._plan: list[Callable[[], None]] = []
        for stream, cb in ((p.stdout, on_stdout), (p.stderr, on_stderr)):
            if stream is not None:
                self._plan.append(_Lines(stream, cb, touch, max_line=max_line, quit_=self._quit, count_cut=self._count_cut).run)
        if stdin is not None and p.stdin is not None:
            self._plan.append(self._feeder(p.stdin, stdin))

    @property
    def splits(self) -> int:
        """How many times a line reached ``max_line`` bytes and was cut."""
        with self._lock:
            return self._splits

    def start(self) -> None:
        """Start every reader and the feeder together (after the caller's replay of held signals, so a raise there leaves none)."""
        self._threads = [threading.Thread(target=work, daemon=True) for work in self._plan]
        for thread in self._threads:
            thread.start()

    def drain(self, seconds: float) -> bool:
        """Wait up to ``seconds`` for every reader to reach EOF and the feeder to finish. -> True when all did."""
        end = time.monotonic() + seconds
        for thread in self._threads:
            thread.join(max(0.0, end - time.monotonic()))
        return not any(thread.is_alive() for thread in self._threads)

    def release(self) -> None:
        """Tell every reader and the feeder to quit, wait until none is inside, then close the child's pipes. Idempotent."""
        self._quit.set()
        for thread in self._threads:
            thread.join()
        for stream in (self._p.stdin, self._p.stdout, self._p.stderr):
            if stream is not None:
                with contextlib.suppress(OSError):
                    stream.close()

    def _count_cut(self) -> None:
        with self._lock:
            self._splits += 1

    def _feeder(self, stream: IO[bytes], data: bytes) -> Callable[[], None]:
        def feed() -> None:
            fd = stream.fileno()
            os.set_blocking(fd, False)
            view = memoryview(data)
            try:
                while view and not self._quit.is_set():
                    if not select.select([], [fd], [], _POLL_S)[1]:
                        continue
                    try:
                        view = view[os.write(fd, view[:_CHUNK]) :]
                    except BlockingIOError:
                        continue
            except OSError:  # BrokenPipeError: the child exited without reading it all
                pass
            finally:
                with contextlib.suppress(OSError):
                    stream.close()  # the end of input; this thread is the only user of the stdin pipe

        return feed
