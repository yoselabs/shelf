"""The vocabulary: what a failure is, what a row can be, what a count looks like."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from any_failure_fp import fingerprint


class Kind(StrEnum):
    """How a failure is treated. Consume it with an exhaustive ``match`` and ``assert_never``."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


class Status(StrEnum):
    """Row states. There is no running state: a key is being worked exactly while some process holds its flock."""

    PENDING = "pending"
    DONE = "done"
    PERMANENT = "permanent"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class Failure:
    kind: Kind
    error: str

    @property
    def fp(self) -> str:
        return fingerprint(self.error)


class ClassifiedError(Exception):
    """Raised by a handler to end its item with a classified failure."""

    def __init__(self, failure: Failure) -> None:
        super().__init__(failure.error)
        self.failure = failure


@dataclass(frozen=True)
class Item:
    """One thing to do. ``payload`` must be JSON-serialisable; a lower ``priority`` is claimed first."""

    key: str
    kind: str = "default"
    payload: object = None
    priority: int = 0


@dataclass(frozen=True)
class Enqueued:
    """What one ``enqueue`` did, read back inside its transaction: the evidence a feeder prints.

    ``new`` rows were inserted, ``existing`` keys were already there (``new + existing`` is the distinct keys given), ``bumped`` of
    those moved to a more urgent priority. ``states`` counts the given keys by their final status, so "already done" is visible.
    """

    new: int
    existing: int
    bumped: int
    states: dict[str, int] = field(default_factory=dict[str, int])


@dataclass(frozen=True)
class Progress:
    """Row counts. ``done`` is a count of rows, never a process exit or a marker file."""

    by_status: dict[Status, int]
    by_kind: dict[str, dict[Status, int]] = field(default_factory=dict[str, dict[Status, int]])

    @property
    def total(self) -> int:
        return sum(self.by_status.values())

    @property
    def done(self) -> int:
        return self.by_status[Status.DONE]


@dataclass(frozen=True)
class RetryRow:
    key: str
    kind: str
    attempts: int
    last_error: str | None
    next_try_at: float
