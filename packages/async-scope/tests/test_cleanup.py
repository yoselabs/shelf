"""cleanup / cleanup_sync — every step is attempted; one failure goes up unchanged, several go up as a group."""

from __future__ import annotations

import asyncio

import pytest
from async_scope import cleanup, cleanup_sync


def _boom(text: str) -> Exception:
    return RuntimeError(text)


async def test_every_step_runs_and_nothing_is_raised_when_all_succeed() -> None:
    log: list[str] = []

    async def slow() -> None:
        await asyncio.sleep(0)
        log.append("async")

    await cleanup(lambda: log.append("sync"), slow, within=2)
    assert log == ["sync", "async"]


async def test_one_failure_propagates_unchanged_and_the_rest_still_ran() -> None:
    log: list[str] = []
    failure = _boom("first")

    def fail() -> None:
        raise failure

    with pytest.raises(RuntimeError) as caught:
        await cleanup(fail, lambda: log.append("after"), within=2)
    assert caught.value is failure
    assert log == ["after"]


async def test_two_failures_are_an_exception_group_in_step_order() -> None:
    a, b = _boom("a"), ValueError("b")

    def fail_a() -> None:
        raise a

    async def fail_b() -> None:
        raise b

    with pytest.raises(ExceptionGroup) as caught:
        await cleanup(fail_a, fail_b, within=2)
    assert caught.value.exceptions == (a, b)


async def test_a_step_over_its_bound_is_a_timeout_failure_and_the_rest_still_ran() -> None:
    log: list[str] = []

    async def hang() -> None:
        await asyncio.sleep(30)

    with pytest.raises(TimeoutError):
        await cleanup(hang, lambda: log.append("after"), within=0.05)
    assert log == ["after"]


async def test_a_cancel_never_strands_the_steps_and_is_not_swallowed() -> None:
    log: list[str] = []

    async def finish() -> None:
        await asyncio.sleep(0.1)
        log.append("finished")

    task = asyncio.ensure_future(cleanup(finish, lambda: log.append("after"), within=2))
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert log == ["finished", "after"]


async def test_a_cancel_and_a_failure_together_are_a_base_exception_group() -> None:
    error = _boom("x")

    def fail() -> None:
        raise error

    async def wait_a_little() -> None:
        await asyncio.sleep(0.05)

    task = asyncio.ensure_future(cleanup(wait_a_little, fail, within=2))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(BaseExceptionGroup) as caught:
        await task
    assert {type(e) for e in caught.value.exceptions} == {asyncio.CancelledError, RuntimeError}
    assert not isinstance(caught.value, ExceptionGroup)


def test_cleanup_sync_runs_every_step_and_raises_one_unchanged() -> None:
    log: list[str] = []
    failure = _boom("only")

    def fail() -> None:
        raise failure

    with pytest.raises(RuntimeError) as caught:
        cleanup_sync(fail, lambda: log.append("after"))
    assert caught.value is failure
    assert log == ["after"]


def test_cleanup_sync_groups_two_and_a_keyboard_interrupt_makes_a_base_group() -> None:
    error = _boom("x")

    def fail() -> None:
        raise error

    def interrupt() -> None:
        raise KeyboardInterrupt

    with pytest.raises(ExceptionGroup):
        cleanup_sync(fail, fail)
    with pytest.raises(BaseExceptionGroup) as caught:
        cleanup_sync(fail, interrupt)
    assert not isinstance(caught.value, ExceptionGroup)
    cleanup_sync()
