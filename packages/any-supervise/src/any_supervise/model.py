"""Spec, replica and result values, and the package's exceptions."""

from __future__ import annotations

import dataclasses
import enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


class SuperviseError(Exception):
    """A recognised failure of this package."""


class SpecError(SuperviseError):
    """The spec file is unreadable or wrong."""


class StateError(SuperviseError):
    """A replica's state file cannot be trusted (corrupt, or without an identity)."""


class BusyError(SuperviseError):
    """Another any-supervise verb holds this state folder's lock."""


class StartFailedError(SuperviseError):
    """A replica was started but its start identity could not be read, so it was stopped again."""


class VersionProbeError(SuperviseError):
    """`version_cmd` failed or printed nothing: the current code version is unknown."""


class UnknownNameError(SuperviseError):
    """A name that is neither a worker, a replica of the spec, nor a state file on disk."""


class StopFailedError(SuperviseError):
    """A replica we own survived SIGTERM, SIGKILL and the proof wait."""

    def __init__(self, replica: str, survivors: tuple[int, ...]) -> None:
        super().__init__(f"{replica}: still alive after SIGKILL: pids {list(survivors)}")
        self.replica = replica
        self.survivors = survivors


class ReplacementDiedError(SuperviseError):
    """A replacement replica exited during its settle time; the roll stops here."""

    def __init__(self, replica: str, log: Path) -> None:
        super().__init__(f"{replica}: the replacement died within its settle time; see {log}")
        self.replica = replica
        self.log = log


class State(enum.StrEnum):
    RUNNING = "running"  # ours, alive, started on the current code version
    STALE = "stale"  # ours, alive, started on another code version
    DEAD = "dead"  # a state file whose process is gone (or whose pid is now another process)
    MISSING = "missing"  # in the spec, no state file: never started or taken down
    ORPHAN = "orphan"  # ours and alive, but no longer in the spec (a count that shrank, a removed worker)


@dataclasses.dataclass(frozen=True, slots=True)
class Worker:
    name: str
    command: tuple[str, ...]
    count: int
    cwd: Path
    log: Path
    env: Mapping[str, str]
    env_pass: tuple[str, ...]
    stop_timeout_s: float


@dataclasses.dataclass(frozen=True, slots=True)
class Replica:
    """Replica `index` (1-based) of `worker`, named `<worker>-<index>`."""

    worker: Worker
    index: int

    @property
    def name(self) -> str:
        return f"{self.worker.name}-{self.index}"

    @property
    def argv(self) -> tuple[str, ...]:
        """The worker's command with `{index}` and `{count}` replaced."""
        return tuple(a.replace("{index}", str(self.index)).replace("{count}", str(self.worker.count)) for a in self.worker.command)

    @property
    def log(self) -> Path:
        return self.worker.log / f"{self.name}.log"


@dataclasses.dataclass(frozen=True, slots=True)
class Spec:
    path: Path
    state: Path
    version_cmd: tuple[str, ...]
    version_cwd: Path
    workers: tuple[Worker, ...]

    @property
    def replicas(self) -> tuple[Replica, ...]:
        return tuple(Replica(w, i) for w in self.workers for i in range(1, w.count + 1))

    def select(self, name: str) -> tuple[Replica, ...]:
        """The replicas a name stands for: a worker's all, or one replica. Raises `UnknownNameError`."""
        found = tuple(r for r in self.replicas if name in {r.worker.name, r.name})
        if not found:
            msg = f"{name!r} is neither a worker nor a replica of {self.path}"
            raise UnknownNameError(msg)
        return found


@dataclasses.dataclass(frozen=True, slots=True)
class Record:
    """What a state file holds: the identity of a started replica."""

    name: str
    pid: int
    start: str
    argv: tuple[str, ...]
    version: str
    started_at: float


@dataclasses.dataclass(frozen=True, slots=True)
class ReplicaStatus:
    name: str
    state: State
    pid: int | None
    version: str | None  # the code version it was started on
    current: str  # the code version `version_cmd` prints now
    started_at: float | None


@dataclasses.dataclass(frozen=True, slots=True)
class Started:
    name: str
    pid: int
    version: str


@dataclasses.dataclass(frozen=True, slots=True)
class Rolled:
    name: str
    old_pid: int | None  # None: nothing of ours was running
    new_pid: int
    version: str


@dataclasses.dataclass(frozen=True, slots=True)
class Stopped:
    name: str
    pid: int
    was_running: bool  # False: the recorded process was already gone; only its state file was removed
