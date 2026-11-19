"""Run items through a pipeline: bounded workers, a semaphore per stage, one item never stops another."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from any_pipeline.frozen import is_frozen
from any_pipeline.outcome import Failed, Ok, Outcome, Report, StageFailed, StageRecord

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from any_pipeline.stage import Flow


class _Run:
    def __init__(self, key: str, records: list[StageRecord], slots: dict[str, asyncio.Semaphore]) -> None:
        self.key = key
        self._records, self._slots = records, slots

    def record(self, record: StageRecord) -> None:
        self._records.append(record)  # one thread, one loop: no lock

    def slot(self, stage: str) -> asyncio.Semaphore:
        return self._slots[stage]


async def run[I, O](pipeline: Flow[I, O], items: Sequence[I], *, key: Callable[[I], str], workers: int) -> Report[O]:
    """Every item goes through the pipeline; a failure is recorded in the Report and the next item carries on."""
    if workers < 1:
        message = f"workers must be at least 1, got {workers}"
        raise ValueError(message)
    for item in items:
        if not is_frozen(item):
            message = f"{type(item).__name__} is not frozen: items are frozen dataclasses, tuples or strings"
            raise TypeError(message)
    names = [key(item) for item in items]
    if len(set(names)) != len(names):
        twice = sorted({n for n in names if names.count(n) > 1})
        message = f"two items have the same key ({', '.join(twice)}): a key is how a record and a result find their item"
        raise ValueError(message)
    slots = {leaf.name: asyncio.Semaphore(leaf.limit.calls) for leaf in pipeline.leaves()}
    records: list[StageRecord] = []
    pending = iter(enumerate(zip(names, items, strict=True)))
    outcomes: list[Outcome[O] | None] = [None] * len(items)

    async def worker() -> None:
        for index, (name, item) in pending:  # one loop, one thread: workers share the iterator safely
            try:
                outcomes[index] = Ok(name, await pipeline.execute(item, _Run(name, records, slots)))
            except StageFailed as failure:
                outcomes[index] = Failed(name, failure.stage, failure.why, failure.cause)

    async with asyncio.TaskGroup() as group:
        for _ in range(min(workers, len(items))):
            group.create_task(worker())
    return Report(tuple(o for o in outcomes if o is not None), tuple(records))


async def run_one[I, O](pipeline: Flow[I, O], item: I, *, key: str) -> O:
    """One item; a failure is raised as the stage's own exception (for a caller that wants a value, not a report)."""
    report = await run(pipeline, [item], key=lambda _i: key, workers=1)
    outcome = report.outcomes[0]
    if isinstance(outcome, Failed):
        raise outcome.cause if outcome.cause is not None else RuntimeError(outcome.why)
    return outcome.value
