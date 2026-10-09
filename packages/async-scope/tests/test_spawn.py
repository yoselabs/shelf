"""ResourceScope.spawn — a background task is stopped and waited for, in its LIFO place."""

from __future__ import annotations

import asyncio
from typing import Self

import pytest
from async_scope import ResourceScope


class _Res:
    def __init__(self, log: list[str], name: str) -> None:
        self.log = log
        self.name = name

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        self.log.append(f"exit:{self.name}")


async def _forever(log: list[str], name: str, *, cleanup: float = 0.0) -> None:
    try:
        await asyncio.Event().wait()
    finally:
        await asyncio.sleep(cleanup)
        log.append(f"stopped:{name}")


async def test_a_task_is_stopped_before_the_resource_it_was_spawned_after() -> None:
    log: list[str] = []
    async with ResourceScope() as scope:
        await scope.enter(_Res(log, "store"))
        scope.spawn(_forever(log, "service"))
        await asyncio.sleep(0)
    assert log == ["stopped:service", "exit:store"]


async def test_aclose_waits_for_the_task_to_finish_its_cleanup() -> None:
    """A bare `task.cancel()` returns at once; the store would close under the cleanup."""
    log: list[str] = []
    async with ResourceScope() as scope:
        await scope.enter(_Res(log, "store"))
        scope.spawn(_forever(log, "service", cleanup=0.05))
        await asyncio.sleep(0)
    assert log == ["stopped:service", "exit:store"]


async def test_tasks_unwind_lifo() -> None:
    log: list[str] = []
    async with ResourceScope() as scope:
        for name in ("a", "b", "c"):
            scope.spawn(_forever(log, name))
        await asyncio.sleep(0)
    assert log == ["stopped:c", "stopped:b", "stopped:a"]


async def test_a_task_that_finished_is_not_an_error() -> None:
    async def quick() -> int:
        return 7

    async with ResourceScope() as scope:
        task = scope.spawn(quick())
        await asyncio.sleep(0)
    assert task.result() == 7


async def test_a_failed_task_is_raised_after_the_rest_unwinds() -> None:
    log: list[str] = []

    async def broken() -> None:
        msg = "service crashed"
        raise RuntimeError(msg)

    scope = ResourceScope()
    await scope.enter(_Res(log, "store"))
    scope.spawn(broken())
    await asyncio.sleep(0)
    with pytest.raises(RuntimeError, match="service crashed"):
        await scope.aclose()
    assert log == ["exit:store"]


async def test_a_cancel_of_the_closer_still_reaches_it() -> None:
    """The task's own CancelledError is swallowed; one aimed at the closer is not."""
    started = asyncio.Event()

    async def stubborn() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            started.set()
            await asyncio.sleep(10)

    scope = ResourceScope()
    task = scope.spawn(stubborn())
    await asyncio.sleep(0)
    closer = asyncio.ensure_future(scope.aclose())
    await started.wait()
    closer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await closer
    task.cancel()
    await asyncio.wait([task])


async def test_a_closed_scope_refuses_a_task() -> None:
    scope = ResourceScope()
    await scope.aclose()

    async def never() -> None:  # pragma: no cover - refused before it runs
        pass

    with pytest.raises(RuntimeError, match="closed"):
        scope.spawn(never())
