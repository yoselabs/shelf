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
from collections.abc import Awaitable, Callable
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

__all__ = ["Lazy", "ResourceScope", "lazy", "memoized"]


class ResourceScope:
    """Owns entered async resources and unwinds them LIFO."""

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
