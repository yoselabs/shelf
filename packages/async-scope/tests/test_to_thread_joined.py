"""to_thread_joined — a cancel never leaves the thread running behind the caller."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest
from async_scope import to_thread_joined


async def test_result_passes_through() -> None:
    assert await to_thread_joined(lambda: 41 + 1) == 42


async def test_runs_off_the_event_loop_thread() -> None:
    loop_thread = threading.get_ident()
    assert await to_thread_joined(threading.get_ident) != loop_thread


async def test_exception_passes_through() -> None:
    def boom() -> None:
        msg = "work failed"
        raise ValueError(msg)

    with pytest.raises(ValueError, match="work failed"):
        await to_thread_joined(boom)


async def test_cancel_waits_for_the_thread_to_finish() -> None:
    """The failure it prevents: asyncio.to_thread returns on cancel while the thread still runs."""
    started = threading.Event()
    finished = threading.Event()

    def work() -> None:
        started.set()
        time.sleep(0.2)
        finished.set()

    task = asyncio.ensure_future(to_thread_joined(work))
    await asyncio.to_thread(started.wait, 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set(), "the cancel propagated while the thread was still running"


async def test_bare_to_thread_does_not_wait() -> None:
    """The hazard itself, so the test above is known to measure something."""
    started = threading.Event()
    finished = threading.Event()

    def work() -> None:
        started.set()
        time.sleep(0.3)
        finished.set()

    task = asyncio.ensure_future(asyncio.to_thread(work))
    await asyncio.to_thread(started.wait, 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not finished.is_set()
    await asyncio.to_thread(finished.wait, 2)


async def test_a_failure_of_the_thread_during_a_cancel_is_not_lost() -> None:
    started = threading.Event()

    def work() -> None:
        started.set()
        time.sleep(0.1)
        msg = "work failed while cancelled"
        raise ValueError(msg)

    task = asyncio.ensure_future(to_thread_joined(work))
    await asyncio.to_thread(started.wait, 2)
    task.cancel()
    with pytest.raises(BaseExceptionGroup) as caught:
        await task
    assert {type(e) for e in caught.value.exceptions} == {asyncio.CancelledError, ValueError}
