"""In-memory stores and the contract every store must pass. No pytest: the contracts are plain functions that raise AssertionError."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from task_spec.model import Task, Trust
from task_spec.ports import Ask, AskKind

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from task_spec.ports import AttentionStore, TaskStore

__all__ = ["InMemoryAttentionStore", "InMemoryTaskStore", "attention_store_contract", "task_store_contract"]


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def all(self) -> Iterable[Task]:
        return list(self._tasks.values())

    def save(self, task: Task) -> None:
        self._tasks[task.id] = task


class InMemoryAttentionStore:
    def __init__(self) -> None:
        self._asks: list[Ask] = []

    def ask(self, ask: Ask) -> None:
        self._asks.append(ask)

    def pending(self) -> Iterable[Ask]:
        return list(self._asks)

    def resolve(self, task_id: str, kind: AskKind) -> Ask | None:
        for index, ask in enumerate(self._asks):
            if ask.task == task_id and ask.kind == kind:
                return self._asks.pop(index)
        return None


def _expect(condition: object) -> None:
    if not condition:
        raise AssertionError


def task_store_contract(make: Callable[[], TaskStore]) -> None:
    store = make()
    _expect(store.get("t-1") is None)
    _expect(list(store.all()) == [])
    task = Task(id="t-1", title="One", why="because", touches=("a/b.py",), acceptance=("just check -> green",))
    store.save(task)
    _expect(store.get("t-1") == task)
    owned = replace(task, trust=Trust.OWNED)
    store.save(owned)
    _expect(store.get("t-1") == owned)
    store.save(Task(id="t-2", title="Two"))
    _expect({t.id for t in store.all()} == {"t-1", "t-2"})


def attention_store_contract(make: Callable[[], AttentionStore]) -> None:
    store = make()
    _expect(list(store.pending()) == [])
    approve = Ask(task="t-1", kind=AskKind.APPROVE, text="raise trust?")
    decide = Ask(task="t-1", kind=AskKind.DECIDE, text="X or Y?")
    store.ask(approve)
    store.ask(decide)
    _expect(list(store.pending()) == [approve, decide])
    _expect(store.resolve("t-1", AskKind.DECIDE) == decide)
    _expect(store.resolve("t-1", AskKind.DECIDE) is None)
    _expect(list(store.pending()) == [approve])
