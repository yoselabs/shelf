"""Async resource lifecycle — LIFO teardown, and lazy thunks that build once.

Two behaviours, both small enough to read in one sitting. If either grows a
resolution order, a graph, or a registry, the wrong thing is being solved: this
is not a DI container, and the point is that it cannot become one.

**Why not `contextlib.AsyncExitStack`.** The stack's `enter_async_context` is
the right shape, and for many callers it is the right answer. It is the wrong
answer when either of these matters:

- **A failing close must not strand the resources beneath it.** `AsyncExitStack`
  unwinds through the exception, which is correct for its contract but means one
  resource refusing to close can leave the rest of the stack open. Here every
  entered resource is exited, and the first exception is re-raised afterwards.
- **`aclose()` must be idempotent.** A lifespan exit and an explicit teardown
  path can both fire; the second must be a no-op, not a double-`__aexit__`.

The subtler guarantee is **record-after-enter**: a resource whose `__aenter__`
raised was never entered, so it must not be on the teardown stack. `enter()`
appends *after* the await returns, never before. Getting this backwards calls
`__aexit__` on a half-built object, which is how a cleanup path becomes the
thing that crashes.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING, Any, Self, TypeAlias, TypeVar

if TYPE_CHECKING:
    from types import TracebackType

_T = TypeVar("_T")

#: A zero-arg async thunk resolving `T` only if awaited.
#:
#: Deliberately a bare alias and not a Protocol or a class: the whole value is
#: that any `async def f() -> T` already satisfies it, so a consumer can hand one
#: over without importing anything. Two implementations ship here — `lazy(value)`
#: for a pre-built value, `memoized(factory)` for a resource built at most once.
Lazy: TypeAlias = Callable[[], Awaitable[_T]]

__all__ = ["Lazy", "ResourceScope", "lazy", "memoized", "to_thread_joined"]


class ResourceScope:
    """Owns entered async resources and spawned tasks, and unwinds them LIFO."""

    def __init__(self) -> None:
        self._entered: list[Any] = []
        self._closed = False

    async def enter(self, resource: _T) -> _T:
        """Enter `resource` if it is an async context manager, and record it.

        A non-context-manager passes through untouched, so a caller can hand
        everything it owns to one scope without sorting by type first.

        Recording happens only after `__aenter__` returns — see the module
        docstring on record-after-enter.
        """
        aenter = getattr(resource, "__aenter__", None)
        if aenter is None:
            return resource
        entered = await aenter()
        self._entered.append(resource)
        return entered  # type: ignore[no-any-return]

    def spawn(self, coro: Coroutine[Any, Any, _T]) -> asyncio.Task[_T]:
        """Run `coro` as a task now; `aclose()` cancels it and waits for it to finish.

        It unwinds in its LIFO place among the entered resources, so a task spawned
        after a resource it uses is gone before that resource closes. Waiting is the
        point: a cancelled task still runs its `finally`, and a bare `task.cancel()`
        lets the scope close what that `finally` touches. A task that failed is
        re-raised by `aclose()` like a failing close; its own cancel is not a failure.
        A closed scope refuses the coroutine rather than leak a task nothing will stop.
        """
        if self._closed:
            coro.close()
            msg = "spawn on a closed ResourceScope"
            raise RuntimeError(msg)
        task = asyncio.ensure_future(coro)
        self._entered.append(_Spawned(task))
        return task

    async def aclose(self) -> None:
        """Unwind LIFO. Idempotent, and does not stop at the first failure.

        Every entered resource is exited even if an earlier one raises; the
        first exception is re-raised once the unwind is complete, so a failure
        is still loud but never costs the resources beneath it.
        """
        if self._closed:
            return
        self._closed = True
        first: BaseException | None = None
        while self._entered:
            resource = self._entered.pop()
            try:
                await resource.__aexit__(None, None, None)
            except Exception as exc:  # noqa: BLE001 — keep unwinding; re-raised below
                first = first or exc
        if first is not None:
            raise first

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()


class _Spawned:
    """A spawned task as a teardown entry: cancel, then wait without being cancelled itself."""

    def __init__(self, task: asyncio.Task[Any]) -> None:
        self._task = task

    async def __aexit__(self, *_: object) -> None:
        self._task.cancel()
        # `wait`, not `await task`: the task's CancelledError must not be mistaken for a
        # cancel of the closer, and a cancel of the closer must still reach the closer.
        await asyncio.wait([self._task])
        if not self._task.cancelled() and (exc := self._task.exception()) is not None:
            raise exc


def lazy(value: _T) -> Lazy[_T]:
    """Wrap an already-built `value` in a thunk matching `Lazy[T]`.

    For injecting a pre-built object where a `Lazy[T]` is expected — a test
    double, or a resource whose construction the caller already owns. The thunk
    yields `value` by identity on every call: no copy, no caching wrapper.
    Callers needing per-call freshness build their own.
    """

    async def _thunk() -> _T:
        return value

    return _thunk


def memoized(factory: Callable[[], Awaitable[_T]]) -> Lazy[_T]:
    """Wrap an async `factory` as a `Lazy[T]` that builds at most once.

    The lock is what makes this worth having over a bare `async def`: without
    it, N concurrent first-callers each run `factory`, which for a browser pool
    or a connection means N of something meant to be one.

    The double check around the lock is not superstition — after first use the
    fast path must not pay for lock acquisition on every resolution.
    """
    lock = asyncio.Lock()
    slot: list[_T] = []

    async def _thunk() -> _T:
        if slot:
            return slot[0]
        async with lock:
            if not slot:
                slot.append(await factory())
        return slot[0]

    return _thunk


async def to_thread_joined(fn: Callable[[], _T]) -> _T:
    """`await asyncio.to_thread(fn)`, except a cancel first waits for `fn` to return.

    `asyncio.to_thread` raises `CancelledError` the moment its task is cancelled, but the
    thread keeps running: Python cannot stop one. Whatever the caller does next — release
    a lock, close the store the thread writes through — then races work it believes is
    finished. Here the cancellation propagates only after the thread is done, so nothing
    the scope tears down is still in use. The cost is plain: a cancel takes as long as the
    work does.
    """
    work = asyncio.ensure_future(asyncio.to_thread(fn))
    try:
        return await asyncio.shield(work)
    except asyncio.CancelledError:
        with contextlib.suppress(BaseException):
            await work
        raise
