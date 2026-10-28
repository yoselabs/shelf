# process-lock

**Stop caring how one process claims a path.** An exclusive `flock` held for as long as the
process wants it; a second process is refused at once, and the kernel lets go when the holder
dies.

```python
import process_lock as pl

lock = pl.ProcessLock.acquire(Path("~/.app/owner.lock").expanduser())
try:
    ...
finally:
    lock.release()          # idempotent; the lock goes with the process's last handle

with pl.ProcessLock.acquire(path):   # or as a context manager
    ...

pl.held()                   # the lock files this process holds now

# wait up to 30 s, telling the user who we wait for; label the record
pl.ProcessLock.acquire(
    path, timeout=30, label="sync", meta={"job": 7},
    on_wait=lambda w: print(f"waiting {w.elapsed:.0f}s for {w.holder}"),
)

pl.holder(path)             # Holder(pid, start, created, label, meta) -- no lock taken
```

## Rules

- **Exclusive.** By default (`timeout=0`) a second process gets `LockHeldError` at once,
  carrying `path`, `holder` and the holder's `pid` when readable (`None` otherwise).
  `timeout=N` waits up to N seconds (`None`: forever), polling and calling
  `on_wait(Waiting(path, elapsed, holder))` each time, then raises.
- **Holder record.** The lock file holds JSON: `pid`, `start` (process start time), `created`,
  free-form `label` and `meta`. `holder(path)` reads it without the lock; no host name.
- **Stale break.** If the record names a dead pid or a pid with another start time while the
  flock is still held (a child kept the descriptor, a lock on a network mount), the waiter
  unlinks the file and locks a fresh one. `break_stale=False` opts out. A `<name>.break`
  guard file serializes breakers and stays beside the lock.
- **Non-reentrant mode.** `reentrant=False`: a second acquire of the path in this process
  waits or raises like any other holder. Re-entry needs both acquirers reentrant.
- **Released by the kernel.** A `flock` dies with its holder, `kill -9` included: no stale
  lock to clean. The record is a hint for messages and the stale break.
- **Re-entrant within a process.** Acquiring twice is two handles on one descriptor; the lock
  goes at the last `release`. Not `lockf`: a POSIX record lock is dropped when *any*
  descriptor on the file closes, so an unrelated `open().close()` would end it.
- **Not inherited.** The descriptor is close-on-exec, so a child process does not keep the
  lock after its parent lets go.
- The lock file is created `0600`, with its parent folders.

POSIX only (`fcntl`). Stdlib only.
