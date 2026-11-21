"""The pump of a held child: line readers for stdout and stderr, a stdin feeder, and the lifetime of the three pipes."""

from __future__ import annotations

import os
import select
import threading
import time
from typing import IO, TYPE_CHECKING

from async_scope import cleanup_sync

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


class PumpStuckError(RuntimeError):
    """``release`` waited ``stuck_after`` seconds and a reader was still inside a callback; nothing was closed.

    ``running`` names the callbacks (``on_stdout``, ``on_stderr``, ``touch``) that had not returned. The pipes stay
    open, because a close under a reader is the race this pump exists to prevent; call ``release`` again once the
    callback returns.
    """

    def __init__(self, running: tuple[str, ...], waited: float) -> None:
        super().__init__(f"a pump callback did not return within {waited}s: {', '.join(running) or 'a reader'}")
        self.running = running


class _Guard:
    """One user callback: after it raises once it is never called again, and the pump keeps that first error."""

    def __init__(self, name: str, fn: Callable[[bytes], None], fail: Callable[[BaseException], None]) -> None:
        self.name, self.fn, self.fail = name, fn, fail
        self.dead = False
        self.inside = False

    def __call__(self, raw: bytes) -> None:
        if self.dead:
            return
        self.inside = True
        try:
            self.fn(raw)
        except BaseException as exc:  # noqa: BLE001 — stored, and raised on the owner by release; the pipes must keep draining
            self.dead = True
            self.fail(exc)
        finally:
            self.inside = False


class _Lines:
    """One reader: the lines (capped pieces) of one pipe to one callback, until EOF or the quit flag."""

    def __init__(
        self,
        stream: IO[bytes],
        cb: _Guard | None,
        touch: _Guard | None,
        *,
        max_line: int,
        quit_: threading.Event,
        count_cut: Callable[[], None],
    ) -> None:
        self.stream, self.cb, self.touch, self.max_line, self.quit, self.count_cut = stream, cb, touch, max_line, quit_, count_cut

    def emit(self, raw: bytes) -> None:
        if self.cb is not None:
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
            chunk = os.read(fd, min(_CHUNK, self.max_line))
            if not chunk:
                return
            if self.touch is not None:
                self.touch(chunk)
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
    ``bytes`` (newline kept, the torn last line too). A callback that raises is not called again and the reading
    goes on to EOF, so the child never blocks on a full pipe; the first error of the pump (any callback, a reader or
    the feeder) is raised by :meth:`release` after the teardown. A line is held at
    most ``max_line`` bytes: a longer one reaches the callback in pieces of exactly ``max_line`` bytes without a
    newline, ``splits`` counts the cuts, so a child that never prints a newline cannot grow memory. ``touch`` runs
    when bytes arrive. ``stdin`` is written as the child takes it and then closed (the end of input); a child that
    exits or stops reading ends the feed quietly. ``None`` writes nothing and leaves the pipe open until release.

    Lifetime, in order: :meth:`start` (once, after any replay), :meth:`drain` (wait for the end of the output),
    :meth:`release` (always, from the owner). Every reader polls its descriptor, so a grandchild that keeps a
    pipe open cannot pin one. Release asks them to quit, waits for every reader and the feeder to be out, and only
    then closes the pipes: no pipe is closed under a thread using it. A callback that has not returned after
    ``stuck_after`` seconds makes release raise :class:`PumpStuckError` with the pipes still open (closing under it
    would be the race); a later release finishes the teardown.
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
        stuck_after: float = 30.0,
    ) -> None:
        check_max_line(max_line)
        self._p = p
        self._stuck_after = stuck_after
        self._error: BaseException | None = None
        self._guards: list[_Guard] = []
        self._quit = threading.Event()
        self._lock = threading.Lock()
        self._splits = 0
        self._threads: list[threading.Thread] = []
        self._plan: list[Callable[[], None]] = []
        touch_guard = None if touch is None else self._guard("touch", lambda _chunk, fn=touch: fn())
        for stream, name, cb in ((p.stdout, "on_stdout", on_stdout), (p.stderr, "on_stderr", on_stderr)):
            if stream is not None:
                reader = _Lines(stream, self._guard(name, cb), touch_guard, max_line=max_line, quit_=self._quit, count_cut=self._count_cut)
                self._plan.append(self._kept(reader.run))
        if stdin is not None and p.stdin is not None:
            self._plan.append(self._kept(self._feeder(p.stdin, stdin)))

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
        """Quit every reader and the feeder, wait until none is inside, close the child's pipes, then raise the first error kept.

        Idempotent. The kept error (a callback, a reader or the feeder failed) is raised once, after the teardown;
        :class:`PumpStuckError` is raised, nothing closed, when a callback has not returned after ``stuck_after`` seconds.
        """
        self._quit.set()
        end = time.monotonic() + self._stuck_after
        for thread in self._threads:
            thread.join(max(0.0, end - time.monotonic()))
        if any(thread.is_alive() for thread in self._threads):
            raise PumpStuckError(tuple(g.name for g in self._guards if g.inside), self._stuck_after) from self._error
        streams = (self._p.stdin, self._p.stdout, self._p.stderr)
        cleanup_sync(*[stream.close for stream in streams if stream is not None], self._raise_kept)

    def _raise_kept(self) -> None:
        with self._lock:
            error, self._error = self._error, None
        if error is not None:
            raise error

    def _guard(self, name: str, fn: Callable[[bytes], None] | None) -> _Guard | None:
        if fn is None:
            return None
        guard = _Guard(name, fn, self._fail)
        self._guards.append(guard)
        return guard

    def _fail(self, exc: BaseException) -> None:
        with self._lock:
            if self._error is None:
                self._error = exc

    def _kept(self, work: Callable[[], None]) -> Callable[[], None]:
        """A thread body whose own failure (not a callback's) is kept for release instead of dying in the thread."""

        def run() -> None:
            try:
                work()
            except BaseException as exc:  # noqa: BLE001 — kept, raised by release
                self._fail(exc)

        return run

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
            except BrokenPipeError:  # the child exited without reading it all
                pass
            finally:
                stream.close()  # the end of input; this thread is the only user of the stdin pipe

        return feed
