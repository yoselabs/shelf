# stream-proc

**Stop caring how a child is run, watched and killed.** One call runs a child in a session of its
own, hands you its stdout and stderr lines as they come, and leaves nothing of it running. Stdlib
only, POSIX.

```python
import threading
from stream_proc import run

stop = threading.Event()
res = run(
    [sys.executable, "-m", "worker", "job"],
    cwd=work, env=env,                     # env as given; None inherits
    on_stdout=log.write, on_stderr=log.write,   # one str per line, newline kept; the torn last line too
    timeout=3600,                          # wall limit, seconds
    idle=300,                              # longest silence on both streams
    stop=stop,                             # set() from any thread: the tree is stopped
    grace=5,                               # SIGTERM to SIGKILL
)
res.returncode   # exit code; None when a signal ended it
res.signal       # that signal's number
res.timed_out    # "wall" | "idle" | "stopped" | None: why *we* stopped it
res.pid, res.pgid, res.start, res.secs
res.survivors    # pids of its tree still alive after the stop (normally ())
```

- **Reader threads drain both pipes**, so a child writing megabytes never blocks. A callback that
  raises is ignored and reading goes on.
- **The stop is the whole tree** (`stop_tree(p, grace=, prove=)`): SIGTERM to the group and to every
  descendant that left it (`setsid`), the grace, SIGKILL to what is left, then a proof loop that
  re-reads `/proc` and kills again until nothing lives. Survivors come back in `Result.survivors`; they
  are never hidden. The caller's own group, parent and pids 0 and 1 are never signalled.
- **Liveness survives pid reuse**: `alive(pid, start)` and `proc_start(pid)` use the start time from
  `/proc/<pid>/stat`. Store `(pid, start)`, never the pid. Zombies count as dead.
- **A SIGTERM during the spawn still stops the child**: `run` swaps the main thread's SIGTERM handler
  while `Popen` runs (`TermHold`, `popen_held`), then replays it where the child is already known. If
  your handler raises, `run` stops the tree and the exception goes on.
- **No `/proc` (macOS)**: no start token, `alive` is signal 0 on the pid, and the stop signals the group
  only; a descendant that left the group is not swept there.
- `run` raises only for a spawn failure (`OSError`) or an exception that unwinds the wait; a child's
  failure is a `Result`.
