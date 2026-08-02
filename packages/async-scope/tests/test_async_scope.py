"""async-scope — the four behaviours, each with the failure it prevents."""

from __future__ import annotations

import asyncio
from typing import Any, Self

import pytest
from async_scope import Lazy, ResourceScope, lazy, memoized


class _Res:
    def __init__(self, log: list[str], name: str, *, fail_enter: bool = False, fail_exit: bool = False) -> None:
        self.log = log
        self.name = name
        self.fail_enter = fail_enter
        self.fail_exit = fail_exit

    async def __aenter__(self) -> Self:
        if self.fail_enter:
            msg = f"{self.name} refused to open"
            raise RuntimeError(msg)
        self.log.append(f"enter:{self.name}")
        return self

    async def __aexit__(self, *_: object) -> None:
        if self.fail_exit:
            msg = f"{self.name} refused to close"
            raise RuntimeError(msg)
        self.log.append(f"exit:{self.name}")


# --- ResourceScope ---


async def test_teardown_is_lifo() -> None:
    log: list[str] = []
    scope = ResourceScope()
    for name in ("a", "b", "c"):
        await scope.enter(_Res(log, name))

    await scope.aclose()

    assert log == ["enter:a", "enter:b", "enter:c", "exit:c", "exit:b", "exit:a"]


async def test_a_failing_close_does_not_strand_the_rest() -> None:
    """The reason this is not `contextlib.AsyncExitStack`.

    Three handles closed in sequence, the first raising: the other two must
    still close. This is the shape of a real defect — three bare `.close()`
    statements in a lifespan, where one raising silently leaks the others.
    """
    log: list[str] = []
    scope = ResourceScope()
    await scope.enter(_Res(log, "outer"))
    await scope.enter(_Res(log, "middle"))
    await scope.enter(_Res(log, "inner", fail_exit=True))

    with pytest.raises(RuntimeError, match="inner refused to close"):
        await scope.aclose()

    assert "exit:middle" in log
    assert "exit:outer" in log


async def test_the_failure_is_still_raised() -> None:
    """The anti-vacuity half. "Keep unwinding" must not become "swallow"."""
    log: list[str] = []
    scope = ResourceScope()
    await scope.enter(_Res(log, "only", fail_exit=True))

    with pytest.raises(RuntimeError, match="only refused to close"):
        await scope.aclose()


async def test_the_first_failure_is_the_one_raised() -> None:
    log: list[str] = []
    scope = ResourceScope()
    await scope.enter(_Res(log, "closed-last", fail_exit=True))
    await scope.enter(_Res(log, "closed-first", fail_exit=True))

    # LIFO, so `closed-first` exits first and its failure is the one surfaced.
    with pytest.raises(RuntimeError, match="closed-first refused to close"):
        await scope.aclose()


async def test_a_resource_that_failed_to_open_is_not_torn_down() -> None:
    """record-after-enter. Exiting a half-built object is how a cleanup path
    becomes the thing that crashes."""
    log: list[str] = []
    scope = ResourceScope()
    await scope.enter(_Res(log, "good"))
    with pytest.raises(RuntimeError, match="bad refused to open"):
        await scope.enter(_Res(log, "bad", fail_enter=True))

    await scope.aclose()

    assert log == ["enter:good", "exit:good"]
    assert not [line for line in log if "bad" in line]


async def test_aclose_is_idempotent() -> None:
    """A lifespan exit and an explicit teardown can both fire."""
    log: list[str] = []
    scope = ResourceScope()
    await scope.enter(_Res(log, "a"))

    await scope.aclose()
    await scope.aclose()

    assert log.count("exit:a") == 1


async def test_a_non_context_manager_passes_through() -> None:
    """So a caller can hand everything it owns to one scope without sorting by type."""
    scope = ResourceScope()
    plain = object()
    assert await scope.enter(plain) is plain
    await scope.aclose()


async def test_scope_works_as_an_async_context_manager() -> None:
    log: list[str] = []
    async with ResourceScope() as scope:
        await scope.enter(_Res(log, "a"))
    assert log == ["enter:a", "exit:a"]


# --- memoized / lazy ---


async def test_memoized_builds_once_under_concurrency() -> None:
    """The reason this is not a bare `async def`.

    Without the lock, N concurrent first-callers each run the factory — N
    browsers, N connections, N model clients. The sleep is what makes the race
    real: an unlocked implementation passes a sequential test.
    """
    builds = 0

    async def _factory() -> object:
        nonlocal builds
        builds += 1
        await asyncio.sleep(0.01)
        return object()

    thunk: Lazy[object] = memoized(_factory)
    results = await asyncio.gather(*(thunk() for _ in range(20)))

    assert builds == 1
    assert all(r is results[0] for r in results)


async def test_memoized_does_not_build_until_awaited() -> None:
    """The whole point at a cold start: constructing costs nothing until used."""
    built = False

    async def _factory() -> object:
        nonlocal built
        built = True
        return object()

    memoized(_factory)
    assert built is False


async def test_memoized_returns_the_same_instance_after_first_use() -> None:
    thunk = memoized(lambda: _identity(object()))
    first = await thunk()
    assert await thunk() is first


async def _identity(value: Any) -> Any:
    return value


async def test_lazy_yields_the_value_by_identity() -> None:
    value = object()
    thunk = lazy(value)
    assert await thunk() is value
    assert await thunk() is value
