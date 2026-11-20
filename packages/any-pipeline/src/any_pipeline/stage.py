"""A stage is a typed value. Composing two that do not fit is a type error; a stage with no limit cannot be written."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, cast, override

from any_pipeline.frozen import is_frozen
from any_pipeline.outcome import StageFailed, StageRecord

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Sequence

type Fn[I, O] = Callable[[I], Coroutine[Any, Any, O]]  # a Coroutine, not an Awaitable: TaskGroup.create_task needs one


@dataclass(frozen=True, slots=True)
class Limit:
    """No default for any number: every stage states how many at once, how long, and how often it may be tried."""

    calls: int
    seconds: float
    tries: int

    def __post_init__(self) -> None:
        if self.calls < 1 or self.tries < 1:
            message = f"calls and tries must be at least 1, got {self}"
            raise ValueError(message)
        if self.seconds <= 0:
            message = f"seconds must be positive, got {self}"
            raise ValueError(message)


class Run(Protocol):
    """What a stage needs from the run that is executing it."""

    key: str

    def record(self, record: StageRecord) -> None: ...

    def slot(self, stage: str) -> asyncio.Semaphore: ...


class Store[O](Protocol):
    async def get(self, key: str) -> O | None: ...

    async def put(self, key: str, value: O) -> None: ...


class MemoryStore[O]:
    def __init__(self) -> None:
        self._values: dict[str, O] = {}

    async def get(self, key: str) -> O | None:
        return self._values.get(key)

    async def put(self, key: str, value: O) -> None:
        self._values[key] = value


class Flow[I, O](ABC):
    """Anything that runs: one Stage, or stages composed. `a >> b` runs b on a's result; `gather(a, b)` runs both on the same input."""

    name: str

    @abstractmethod
    def leaves(self) -> tuple[Stage[Any, Any], ...]: ...  # Any: stages of every item type live in one tree

    @abstractmethod
    async def execute(self, item: I, run: Run) -> O: ...

    def __rshift__[P](self, nxt: Flow[O, P]) -> Flow[I, P]:
        return _Chain(self, nxt)

    def otherwise(self, fallback: Callable[[str], O]) -> Flow[I, O]:
        """A failure of this flow becomes `fallback(why)` instead of failing the item. The record still shows the failure."""
        return _Otherwise(self, fallback)

    def __str__(self) -> str:
        return self.name


class Stage[I, O](Flow[I, O]):
    """One async function with its limit."""

    def __init__(self, name: str, fn: Fn[I, O], limit: Limit) -> None:
        self.name, self.fn, self.limit = name, fn, limit

    @override
    def leaves(self) -> tuple[Stage[Any, Any], ...]:  # Any: stages of every item type live in one tree
        return (self,)

    @override
    async def execute(self, item: I, run: Run) -> O:
        started = time.monotonic()
        why, tries, cause = "never ran", 0, RuntimeError("never ran")
        async with run.slot(self.name):
            for tries in range(1, self.limit.tries + 1):
                try:
                    async with asyncio.timeout(self.limit.seconds):
                        out = await self.fn(item)
                except Exception as error:  # noqa: BLE001  a stage failure is data for the report, not a crash
                    why, cause = f"{type(error).__name__}: {error}"[:300], error
                    continue
                if is_frozen(out):
                    run.record(StageRecord(run.key, self.name, time.monotonic() - started, tries, ok=True, skipped=False))
                    return out
                why = f"returned a {type(out).__name__}, which is not frozen (use a frozen dataclass, tuple or str)"
                cause = TypeError(why)
                break
        run.record(StageRecord(run.key, self.name, time.monotonic() - started, tries, ok=False, skipped=False))
        raise StageFailed(self.name, why, cause)


class Persistent[I, O](Stage[I, O]):
    """A stage whose result is kept under `key(item)`: the next run finds it and does not call the function."""

    def __init__(self, name: str, fn: Fn[I, O], limit: Limit, *, key: Callable[[I], str], store: Store[O]) -> None:
        super().__init__(name, fn, limit)
        self._key, self._store = key, store

    @override
    async def execute(self, item: I, run: Run) -> O:
        key = self._key(item)
        kept = await self._store.get(key)
        if kept is not None:
            run.record(StageRecord(run.key, self.name, 0.0, 0, ok=True, skipped=True))
            return kept
        out = await super().execute(item, run)
        await self._store.put(key, out)
        return out


class _Chain[I, M, O](Flow[I, O]):
    def __init__(self, first: Flow[I, M], second: Flow[M, O]) -> None:
        self._first, self._second = first, second
        self.name = f"{first.name} >> {second.name}"
        _unique(self.leaves())

    @override
    def leaves(self) -> tuple[Stage[Any, Any], ...]:
        return (*self._first.leaves(), *self._second.leaves())

    @override
    async def execute(self, item: I, run: Run) -> O:
        return await self._second.execute(await self._first.execute(item, run), run)


class _Otherwise[I, O](Flow[I, O]):
    def __init__(self, inner: Flow[I, O], fallback: Callable[[str], O]) -> None:
        self._inner, self._fallback = inner, fallback
        self.name = inner.name

    @override
    def leaves(self) -> tuple[Stage[Any, Any], ...]:
        return self._inner.leaves()

    @override
    async def execute(self, item: I, run: Run) -> O:
        try:
            return await self._inner.execute(item, run)
        except StageFailed as failure:
            return self._fallback(failure.why)


class _Gather[I](Flow[I, tuple[Any, ...]]):  # the arity is erased here and restored by the typed gather() overloads
    def __init__(self, stages: Sequence[Flow[I, Any]]) -> None:
        self._stages = tuple(stages)
        self.name = "gather(" + ", ".join(s.name for s in stages) + ")"
        _unique(self.leaves())

    @override
    def leaves(self) -> tuple[Stage[Any, Any], ...]:
        return tuple(leaf for s in self._stages for leaf in s.leaves())

    @override
    async def execute(self, item: I, run: Run) -> tuple[Any, ...]:
        try:
            async with asyncio.TaskGroup() as group:
                tasks = [group.create_task(s.execute(item, run)) for s in self._stages]
        except* StageFailed as failures:
            raise failures.exceptions[0] from None  # the first failure is the report's; the TaskGroup already cancelled the rest
        return tuple(t.result() for t in tasks)


def _unique(leaves: Sequence[Stage[Any, Any]]) -> None:
    names = [leaf.name for leaf in leaves]
    twice = sorted({n for n in names if names.count(n) > 1})
    if twice:
        message = f"stage name used twice: {', '.join(twice)} (a name is how a limit and a record find their stage)"
        raise ValueError(message)


def gather[I, A, B](a: Flow[I, A], b: Flow[I, B], /) -> Flow[I, tuple[A, B]]:
    return cast("Flow[I, tuple[A, B]]", _Gather((a, b)))


def gather3[I, A, B, C](a: Flow[I, A], b: Flow[I, B], c: Flow[I, C], /) -> Flow[I, tuple[A, B, C]]:
    return cast("Flow[I, tuple[A, B, C]]", _Gather((a, b, c)))


def gather4[I, A, B, C, D](a: Flow[I, A], b: Flow[I, B], c: Flow[I, C], d: Flow[I, D], /) -> Flow[I, tuple[A, B, C, D]]:
    return cast("Flow[I, tuple[A, B, C, D]]", _Gather((a, b, c, d)))


def blocking[I, O](fn: Callable[[I], O]) -> Fn[I, O]:
    """A plain function as a stage function. It runs in a thread, which cannot be cancelled: a time limit abandons it, not stops it."""

    async def call(item: I) -> O:
        return await asyncio.to_thread(fn, item)

    return call
