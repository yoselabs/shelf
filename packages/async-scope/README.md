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

## Serving an ASGI app — `async_scope.asgi`

Install `async-scope[asgi]`. Separate module, lazy uvicorn import, so the package
root stays dependency-free.

```python
from async_scope.asgi import serve_asgi

async with serve_asgi(app) as base_url:      # http://127.0.0.1:<free port>
    ...                                       # the server is up before the body runs
```

It is here rather than in its own package because all three things it knows are
ways a scope fails to close, which is what the rest of this package is about.
None of them is a misuse of uvicorn, and every one was paid for.

**A previous serve poisons the next one.** sse-starlette monkey-patches uvicorn
and copies the server's `should_exit` into its module-global `AppStatus.should_exit`
— and never resets it. The flag that stopped server #1 is still set when server #2
starts, and aborts its first streaming response with *"ASGI callable returned
without completing response"*. Serial serves in one process — a test suite, a
restarted daemon — break, and the failure points at the innocent second server.
Cleared before every serve — through `sys.modules`, never an import: sse-starlette is
not a dependency here and must not become one, and if nothing loaded it there is no
global to poison.

**`force_exit` is not enough to stop a stuck server.** `should_exit` alone asks for
a graceful shutdown, which waits for open connections to drain; a server-sent-event
stream or a request blocked on a subprocess never drains. `force_exit` is documented
to skip that wait and is set — but measured against uvicorn 0.51 with a handler
holding an open response, `serve()` does not return at all. So the wait is a short
grace (`shutdown_grace`, ~0.15s is what a clean exit actually costs) and then the
task is cancelled outright. Teardown never wedges and never pays an open-ended wait.

**A failed startup is a `SystemExit`, not an exception.** uvicorn is written to be a
program, so an app that raises during lifespan ends in `sys.exit(3)`. That matters
inside someone else's event loop: `Task` special-cases `SystemExit`, storing it *and*
re-raising it into the loop, which stops the loop and cancels whatever was awaiting.
A caller who wraps the serve in `try/except` therefore gets a `CancelledError` from
its own runner, after unwinding has started, with the real cause only in the log. It
is converted to `ServeError` inside the task, which is the only place early enough.

`bind_loopback(host, port=0)` is the port half: ask the kernel for a free one rather
than picking a number, which is what a fixed port turns into as soon as two tests run
at once.

## Surface

- `ResourceScope` — `enter(resource)`, `aclose()`, and async-context-manager use.
- `memoized(factory) -> Lazy[T]` — build at most once, concurrency-safe.
- `lazy(value) -> Lazy[T]` — a pre-built value as a thunk.
- `Lazy[T]` — `Callable[[], Awaitable[T]]`.
- `async_scope.asgi` (extra `asgi`) — `serve_asgi`, `bind_loopback`, `LOOPBACK`, `ServeError`.
