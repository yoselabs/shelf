"""The loop: claim, run the handler, finish by what it did, stop after a quiet spell."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from any_work.model import ClassifiedError, Failure, Kind

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from any_work.work import Claimed, Work


async def drain(
    work: Work,
    handler: Callable[[Claimed], Awaitable[None]],
    *,
    concurrency: int = 1,
    idle_exit_s: float = 30.0,
    poll_s: float = 1.0,
    kind: str | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Run ``handler`` over claimable items with ``concurrency`` workers until none was claimable for ``idle_exit_s``.

    The handler returns for ok, raises :class:`ClassifiedError` for a classified failure, and any other exception
    ends the item as an unknown failure (retried to the cap, never permanent). The handler commits its result before it returns.
    An item whose retry lies further ahead than ``idle_exit_s`` is left for the next drain.
    """

    async def worker() -> None:
        idle_since = clock()
        while True:
            claimed = work.claim(kind)
            if claimed is None:
                if clock() - idle_since >= idle_exit_s:
                    return
                await sleep(poll_s)
                continue
            with claimed:
                await _run(handler, claimed)
            idle_since = clock()

    async with asyncio.TaskGroup() as group:
        for _ in range(concurrency):
            group.create_task(worker())


async def _run(handler: Callable[[Claimed], Awaitable[None]], claimed: Claimed) -> None:
    try:
        await handler(claimed)
    except ClassifiedError as error:
        outcome: Failure | None = error.failure
    except Exception as error:  # noqa: BLE001 - an unclassified error is exactly the unknown kind
        outcome = Failure(Kind.UNKNOWN, f"{type(error).__name__}: {error}")
    else:
        outcome = None
    if not claimed.finished:
        claimed.finish(outcome)
