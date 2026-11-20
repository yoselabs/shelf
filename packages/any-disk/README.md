# any-disk

**Stop hand-rolling the disk check in a long loop.** Two levels of free space give three zones; the call waits in the
middle one and answers a bool. Stdlib only.

```python
from any_disk import await_space, await_space_async

# below 50 GiB free: wait (poll every 5 min); below 40 GiB: stop
if not await_space("/data", wait_below_gb=50, stop_below_gb=40, on_wait=lambda free: print(f"{free:.0f} GiB free, waiting")):
    raise SystemExit("disk nearly full")

ok = await await_space_async("/data", wait_below_gb=50, stop_below_gb=40)   # same, awaits asyncio.sleep
```

## Rules

| free space | result |
|---|---|
| `>= wait_below_gb` | `True` at once |
| `stop_below_gb <= free < wait_below_gb` | `on_wait(free_gb)`, sleep `poll` seconds (default 300), read again |
| `< stop_below_gb` | `False` at once, also when the disk falls there during a wait |

- `verdict(free_gb, wait, stop)` is the pure core and `space_verdict(path, ...)` one reading of the disk ("room", "wait" or "stop"); the two `await_*` helpers are only a loop over it.
- GiB: `shutil.disk_usage(path).free / 1024**3`, not decimal GB.
- `stop_below_gb > wait_below_gb` raises `ValueError`.
- Waits forever while the disk stays between the levels: bound it from the caller (cancel the task, or a timer that kills the process) if that matters.
- `sleep` and `disk_usage` are injectable (tests, or a fake clock); `await_space_async` takes an awaitable `sleep`.
