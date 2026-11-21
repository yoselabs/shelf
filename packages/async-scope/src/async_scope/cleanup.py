"""Run every cleanup step, whatever the earlier ones did, and say what failed.

The shape of the failure is the contract (constitution Article III, "no silent failures"):

- no step failed: return;
- one failed: that exception goes up unchanged, so a caller can ``except`` it by type;
- two or more failed: an :class:`ExceptionGroup`, in step order. If a cancellation or ``KeyboardInterrupt``
  is among them it is a :class:`BaseExceptionGroup` (the constructor picks the class), so a cancel is never
  absorbed into an ordinary error and never dropped.

Nothing is suppressed: a cleanup that may legitimately find nothing to do (the resource is already gone)
checks for that and returns; it does not raise and hide.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence


def raise_failures(errors: Sequence[BaseException]) -> None:
    """Raise nothing, the one error unchanged, or the group of several (a base group when any is not an ``Exception``)."""
    if len(errors) == 1:
        raise errors[0]
    if errors:
        msg = "cleanup failed"
        raise BaseExceptionGroup(msg, list(errors))


def cleanup_sync(*steps: Callable[[], object]) -> None:
    """Call every step in order; raise what failed as described in the module docstring."""
    errors: list[BaseException] = []
    for step in steps:
        try:
            step()
        except BaseException as exc:  # noqa: BLE001 — every step must run; raise_failures re-raises all of them
            errors.append(exc)
    raise_failures(errors)


async def cleanup(*steps: Callable[[], Awaitable[object] | object], within: float) -> None:
    """Run every step in order (a plain function or an ``async`` one), each shielded and bounded by ``within`` seconds.

    A step runs in a task of its own that a cancel of the caller does not stop: the caller's cancel is held
    until the step is done (or its bound passes), the remaining steps still run, and the cancel is raised at
    the end with any failures. A step over ``within`` is cancelled and counts as a ``TimeoutError`` failure.
    Steps run outside the caller's task, so a resource bound to its entering task (an anyio cancel scope) belongs
    in a :class:`async_scope.ResourceScope` instead.
    """
    errors: list[BaseException] = []
    for step in steps:
        try:
            await _bounded(step, within)
        except BaseException as exc:  # noqa: BLE001 — every step must run; raise_failures re-raises all of them
            errors.append(exc)
    raise_failures(errors)


async def _call(step: Callable[[], Awaitable[object] | object]) -> None:
    result = step()
    if inspect.isawaitable(result):
        await result


def _consume(task: asyncio.Task[None]) -> None:
    if not task.cancelled():
        task.exception()  # retrieved: the failure is reported by `_bounded`, not by the loop's "never retrieved" log


async def _bounded(step: Callable[[], Awaitable[object] | object], within: float) -> None:
    task = asyncio.ensure_future(_call(step))
    task.add_done_callback(_consume)
    try:
        async with asyncio.timeout(within):
            await asyncio.shield(task)
    except asyncio.CancelledError as cancel:
        await asyncio.wait({task}, timeout=within)  # the cancel is the caller's; the step still gets to finish, bounded
        task.cancel()
        failure = task.exception() if task.done() and not task.cancelled() else None
        if failure is not None:
            msg = "cleanup failed"
            raise BaseExceptionGroup(msg, [cancel, failure]) from None
        raise
    except TimeoutError:
        task.cancel()
        raise
