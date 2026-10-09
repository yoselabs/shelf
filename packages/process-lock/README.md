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
```

## Rules

- **Exclusive, non-blocking.** A second process gets `LockHeldError` at once, carrying the
  `path` and the holder's `pid` when the holder wrote one (`None` otherwise).
- **Released by the kernel.** A `flock` dies with its holder, `kill -9` included: no stale
  lock to clean, no pid to trust. The pid in the file is a hint for a message, nothing more.
- **Re-entrant within a process.** Acquiring twice is two handles on one descriptor; the lock
  goes at the last `release`. Not `lockf`: a POSIX record lock is dropped when *any*
  descriptor on the file closes, so an unrelated `open().close()` would end it.
- **Not inherited.** The descriptor is close-on-exec, so a child process does not keep the
  lock after its parent lets go.
- The lock file is created `0600`, with its parent folders.

POSIX only (`fcntl`). Stdlib only.
