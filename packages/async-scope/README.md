# async-scope

**Stop hand-rolling resource teardown.** A LIFO scope that never strands what it
holds, and lazy thunks that build at most once under concurrency.

```python
from async_scope import Lazy, ResourceScope, lazy, memoized

scope = ResourceScope()
db = await scope.enter(Database(...))        # entered, and recorded for teardown
await scope.aclose()                          # LIFO, idempotent, never strands

browser: Lazy[Browser] = memoized(launch)     # built on first await, once
fake: Lazy[Browser] = lazy(FakeBrowser())     # a pre-built value as a thunk
```

## Why not `contextlib.AsyncExitStack`

Often it is the right answer. It is the wrong one when either of these matters:

- **A failing close must not strand the resources beneath it.** `AsyncExitStack`
  unwinds through the exception — correct for its contract, but one resource
  refusing to close can leave the rest of the stack open. `aclose()` exits every
  entered resource and re-raises the first exception afterwards.
- **`aclose()` must be idempotent.** A framework lifespan exit and an explicit
  teardown path can both fire; the second must be a no-op.

And the guarantee that is easy to get backwards: **record-after-enter.** A
resource whose `__aenter__` raised was never entered, so it is not on the
teardown stack. Appending before the await is how a cleanup path becomes the
thing that crashes, by calling `__aexit__` on a half-built object.

## Why `memoized` and not a bare `async def`

The lock. Without it, N concurrent first-callers each run the factory — which
for a browser pool, a connection, or a model client means N of something meant
to be one. The double check around the lock keeps the post-first-use fast path
free of acquisition.

`Lazy[T]` is a bare alias for `Callable[[], Awaitable[T]]`, not a Protocol or a
class, so any `async def f() -> T` already satisfies it and a consumer can hand
one over without importing anything.

## What this is not

Not a DI container. There is no registry, no resolution order, no graph. A
container exists to resolve an *unknown* dependency graph; if you know your
graph where you write it — and most applications do — these two behaviours are
what you actually needed from one.

## Surface

- `ResourceScope` — `enter(resource)`, `aclose()`, and async-context-manager use.
- `memoized(factory) -> Lazy[T]` — build at most once, concurrency-safe.
- `lazy(value) -> Lazy[T]` — a pre-built value as a thunk.
- `Lazy[T]` — `Callable[[], Awaitable[T]]`.
