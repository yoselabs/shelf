# mcp SDK leaks one memory receive stream per SSE reply

Verdict: upstream, not shelf code. A plain `uvicorn.Server` and a plain `fastmcp.Client`, with no shelf package, leak the same way.
Report text below is ready to paste; no upstream issue is opened yet.

## Versions

mcp 1.28.1, fastmcp 3.4.4, sse-starlette 3.4.5, uvicorn 0.51.0, anyio 4.14.1, starlette 1.3.1, Python 3.12, macOS.

## Symptom

```
ResourceWarning: Unclosed <MemoryObjectReceiveStream at 0x...>
```

Raised from `anyio/streams/memory.py` `__del__`, so it surfaces as an unraisable warning at an arbitrary garbage collection
(`PytestUnraisableExceptionWarning` under `filterwarnings = error`). One per tool call. Also printed once at exit:
`Task was destroyed but it is pending! ... _shutdown_watcher() ... sse_starlette/sse.py:136` (a stderr line, not a warning).

## Cause

`mcp/server/streamable_http.py`, `_handle_post_request`, the SSE branch: `sse_stream_writer, sse_stream_reader = anyio.create_memory_object_stream(0)`
hands `sse_stream_reader` to `EventSourceResponse(content=...)`. Only the `except Exception` path calls `sse_stream_reader.aclose()`. On a
normal reply nobody closes it (the writer is closed by `_run_sse_writer`; the reader never is). The same holds for the standalone GET stream.

## Minimal reproducer

```python
import asyncio, gc, socket, sys, warnings
import uvicorn
from fastmcp import Client, FastMCP

warnings.simplefilter("error")
unraisable = []
sys.unraisablehook = lambda u: unraisable.append(repr(u.exc_value))

mcp = FastMCP("t")

@mcp.tool
def ping() -> str:
    return "pong"

async def one():
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); sock.listen(16)
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(mcp.http_app(), log_level="warning", lifespan="on"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    while not server.started:
        await asyncio.sleep(0.02)
    async with Client(f"http://127.0.0.1:{port}/mcp") as c:
        await c.call_tool("ping")
    server.should_exit = True
    await task
    sock.close()

async def main():
    for _ in range(3):
        await one()
    gc.collect(); await asyncio.sleep(0.2); gc.collect()

asyncio.run(main())
gc.collect()
print("unraisable:", len(unraisable))   # 12 on the versions above
```

## Shelf workaround

`async_scope.testing.close_leaked_memory_streams`: an autouse pytest fixture that holds every `MemoryObjectReceiveStream` a test creates and
closes them at teardown. Imported by the `conftest.py` of `packages/mcp-call` and `packages/mcp-bridge`. Delete it, and the extra
`async-scope[testing]`, when the upstream fix lands.
