"""The ports a task tracker and the owner's attention queue implement."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable

    from task_spec.model import Task


class AskKind(StrEnum):
    """A task ask ends in one typed edit of the task. ``release`` is reserved."""

    APPROVE = "approve"
    ATTEST = "attest"
    DECIDE = "decide"
    FACT = "fact"
    REVIEW = "review"
    REWRITE = "rewrite"
    TRIAGE = "triage"
    SPLIT = "split"
    CONFLICT = "conflict"
    UNBLOCK = "unblock"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class Ask:
    """A question to the owner about one task."""

    task: str
    kind: AskKind
    text: str


class TaskStore(Protocol):
    """Where tasks live. ``save`` creates or replaces by id."""

    def get(self, task_id: str) -> Task | None: ...

    def all(self) -> Iterable[Task]: ...

    def save(self, task: Task) -> None: ...


class AttentionStore(Protocol):
    """The owner's queue. ``resolve`` removes the ask and returns it, or ``None`` when none is waiting."""

    def ask(self, ask: Ask) -> None: ...

    def pending(self) -> Iterable[Ask]: ...

    def resolve(self, task_id: str, kind: AskKind) -> Ask | None: ...
