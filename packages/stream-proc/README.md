# stream-proc

**Stop caring how a child is run, watched and killed.** One call runs a child in a session of its
own, hands you its stdout and stderr lines as they come, and leaves nothing of it running. Stdlib
only (`ctypes` on macOS), POSIX.

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
  re-reads the process table and kills again until nothing lives. Survivors come back in `Result.survivors`; they
  are never hidden. The caller's own group, parent and pids 0 and 1 are never signalled.
- **Liveness survives pid reuse**: `alive(pid, start)` and `proc_start(pid)` use the process start time
  (`/proc/<pid>/stat` on Linux; `pbi_start_tvsec`/`tvusec` of libproc on macOS). Store `(pid, start)`, never
  the pid. Zombies count as dead.
- **A group's liveness needs no table**: `group_alive(pgid)` is `os.killpg(pgid, 0)` (a group we may not
  signal still counts as alive; ids 0 and 1 and below are False). Use it with the `pgid` of a `Result`.
- **One process table on both OSes**: `table() -> dict[int, Proc]` (`pid, ppid, pgid, sid, start, state,
  cpu_s, cmd`) and `descendants(root, rows=None)`. Linux reads `/proc`; macOS calls `libproc` through
  `ctypes` (`proc_listpids`, `proc_listchildpids`, `proc_pidinfo`), all inside `stream_proc.procmac`, loaded
  lazily and only on macOS. On macOS `sid` is 0 and `cmd` is the short command name; `cpu_s` is 0.0 for
  another user's process.
- **A SIGTERM or Ctrl-C during the spawn still stops the child**: `run` swaps the main thread's SIGTERM
  and SIGINT handlers while `Popen` runs (`TermHold`, `popen_held`), then replays them where the child is
  already known. If a handler raises (SIGINT's default raises KeyboardInterrupt), `run` stops the tree and
  the exception goes on.
- **macOS has the same stop**: start token, descendant sweep and proof work as on Linux. Only if libproc
  cannot load does it degrade to signal 0 on the pid and the group alone.
- `run` raises only for a spawn failure (`OSError`) or an exception that unwinds the wait; a child's
  failure is a `Result`.
