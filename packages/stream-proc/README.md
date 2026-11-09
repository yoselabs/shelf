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

## Capture and stopping a pid we did not spawn

```python
from stream_proc import capture, capture_bytes, stop_pid

got = capture(["git", "status"], cwd=repo, timeout=30, tick=heartbeat)   # tick: every 0.2 s while it lives, once after
got.exit        # the exit code; 124 on a timeout (tree stopped); -N when signal N ended it
got.out, got.err, got.secs, got.timed_out, got.survivors

raw = capture_bytes(["cat"], input=b"\xff\r\n", timeout=30)   # exact bytes: raw.out == b"\xff\r\n"
capture_bytes(argv, capture=False, stdin=None)                  # child writes to our stdout/stderr; out/err are b""

stop_pid(pid, start)   # a recorded holder, a server from an earlier run: stops its tree, -> pids still alive
```

- **`capture` is `capture_bytes` decoded**: both streams as one `str` each (UTF-8, bad bytes replaced), the
  same wall timeout and tree stop. There is no size cap; all output is held in memory.
- **`capture_bytes(argv, cwd=, env=, timeout=, input=, stdin=subprocess.DEVNULL, capture=True, grace=, drain=2.0)`** is
  `capture` for bytes, and `capture` is built on it (it only decodes): `out`/`err` are the exact bytes (no decoding,
  `\r\n` kept) in a `CapturedBytes` (`exit, out, err, secs, timed_out, survivors`). `stdin` is a `subprocess` value:
  `DEVNULL` (default), `None` (inherit ours), an fd or a file. `input` instead feeds bytes through a pipe while output
  is read, so large in and out never deadlock, and a child that exits without reading it all is no error; `input` with a
  non-default `stdin` raises `ValueError`. `capture=False` inherits stdout/stderr (both come back `b""`).
- **No controlling terminal**: every child is a session leader (`start_new_session`), so with `stdin=None` and/or
  `capture=False` it shares our descriptors but has no controlling tty: no job control, no `/dev/tty`, no tty-driven
  SIGINT from Ctrl-C (the caller's own SIGINT still stops the tree). Do not use it for an interactive child.
- **`timeout` and `drain`**: the wait is on the child, not its pipes. `timeout` is the wall limit for the child; at
  the limit the tree is stopped, exit 124, `timed_out=True`, partial bytes in `out`/`err`, no exception (unlike
  `subprocess.run`). After the child ends the pipes are read for at most `drain` more seconds, so a process that
  outlived the child and holds a pipe (`sh -c "sleep 30 & echo hi"`) costs `drain`, not its lifetime, and the result
  is the child's real exit code. A SIGTERM/SIGINT during the spawn or any unwinding exception stops the tree first.
  No `tick`, no size cap.
- **`stop_pid` signals only the process it names**: the pid must still carry the `start` token you
  stored (`proc_start(pid)`; `None` takes the current token). A reused pid, a dead one or a system with no
  process table returns `()` and sends no signal. `PidHandle` is the `Popen` look-alike `stop_tree` takes.
- **Limits**: the token check and the signal are two steps, so a pid reused in that gap can still be hit. With
  no `start` token (`None` or empty and the pid already gone) there is no reuse protection: always store `proc_start`.

`popen_registered(argv, registered=..., cwd=..., env=...)` starts a child behind an
isolated installed Python exec gate. The callback receives `OwnedProcess(pid, pgid,
start, boot)` and must durably register it before returning. EOF, invalid permission,
callback failure and held signal replay cannot execute the target. Prompt stdin and
stdout/stderr remain separate from private control pipes. Target exec errors raise
native OSError; exact argv/environment/cwd and PID/session are preserved.

`inspect_process(pid)` and `observe_owned(identity)` return `ProcessObservation`:
matching, gone, different_process or unknown. A missing boot/native identity refuses
registered spawn. Observation concerns the leader only; it is not whole-tree stop
proof. Registration callbacks must use their own bounded persistence operation.
Successful spawn reports registered permission, not proof that target code ran.
Coordinator restart/result collection and surviving-workload custody are separate.

If permission transmission has begun and its acknowledgment is interrupted,
`RegisteredStartUncertainError` retains the registered identity and `leader_reaped`.
Its chained cause retains the original interruption. The target may have executed;
leader cleanup does not establish whole-workload stop. Confirmed private exec
rejection still raises the native OSError instead of uncertainty.
