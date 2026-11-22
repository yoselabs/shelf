"""Process readiness stages, progress and live blockers, independent of the web adapter."""

from __future__ import annotations

import contextlib
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

Event: TypeAlias = Literal["start", "progress", "end", "ready", "refused"]
Listener: TypeAlias = "Callable[[Event, Stage], None]"
Blocker: TypeAlias = "Callable[[], Stage | None]"


@dataclass(frozen=True)
class Stage:
    """One condition the service waits for, including optional measured progress."""

    name: str
    message: str
    done: int | None = None
    total: int | None = None
    files: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        """The complete public health view of this stage."""
        out: dict[str, object] = {"stage": self.name, "message": self.message}
        if self.total is not None:
            out["progress"] = {"done": self.done or 0, "total": self.total}
        if self.files:
            out["files"] = list(self.files)
        return out


STARTING = Stage("starting", "the server is starting")
READY = Stage("ready", "ready")


class Readiness:
    """Own boot stages, a persistent refusal, listeners and dynamically checked blockers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running: Stage | None = STARTING
        self._booted = False
        self._refused: Stage | None = None
        self._blockers: list[Blocker] = []
        self._listeners: list[Listener] = []

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Subscribe until the returned callable removes the listener."""
        with self._lock:
            self._listeners.append(listener)

        def remove() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return remove

    def add_blocker(self, blocker: Blocker) -> Callable[[], None]:
        """Hold readiness while the callback returns a stage; return its remover."""
        with self._lock:
            self._blockers.append(blocker)

        def remove() -> None:
            with self._lock:
                if blocker in self._blockers:
                    self._blockers.remove(blocker)

        return remove

    @contextlib.contextmanager
    def stage(self, name: str, message: str) -> Generator[None]:
        """Begin a stage for the body; leave a failed stage visible to the refusal."""
        self._set(Stage(name, message), "start")
        yield
        with self._lock:
            ended, self._running = self._running, None
        if ended is not None:
            self._emit("end", ended)

    def progress(self, done: int, total: int) -> None:
        """Report measured progress in the running stage."""
        with self._lock:
            running = self._running
        if running is not None and running is not STARTING:
            self._set(Stage(running.name, running.message, done, total, running.files), "progress")

    def ready(self) -> None:
        """Finish boot; live blockers can still hold the service back."""
        with self._lock:
            self._running, self._booted = None, True
        self._emit("ready", READY)

    def refuse(self, reason: str) -> None:
        """Permanently refuse this boot with a visible reason."""
        refused = Stage("refused", reason)
        with self._lock:
            self._refused = refused
        self._emit("refused", refused)

    def current(self) -> Stage:
        """Refusal wins over blockers, which win over the current boot stage."""
        with self._lock:
            refused, running, booted, blockers = self._refused, self._running, self._booted, tuple(self._blockers)
        if refused is not None:
            return refused
        for blocker in blockers:
            if (held := blocker()) is not None:
                return held
        return running if running is not None else READY if booted else STARTING

    def _set(self, stage: Stage, event: Event) -> None:
        with self._lock:
            self._running = stage
        self._emit(event, stage)

    def _emit(self, event: Event, stage: Stage) -> None:
        with self._lock:
            listeners = tuple(self._listeners)
        for listener in listeners:
            listener(event, stage)
