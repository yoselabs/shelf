# any-proc

**Stop caring how a child process is started, limited, read back and kept alive.** Two
modules, imported by name; stdlib only, POSIX.

## `any_proc.run` — run a child once

```python
from any_proc.run import ArgsError, Limits, call

out = call(
    [sys.executable, "-m", "my_worker", "job.py"],
    args={"path": "raw/x.pdf"},          # a JSON object on stdin, at most 64 KiB encoded
    env=env, timeout=600,
    limits=Limits(memory_bytes=2 << 30, file_size_bytes=512 << 20, process_headroom=256),
)
out.result      # the JSON object on the child's last marked line, or None
out.timed_out   # True: killed at the timeout, returncode is None
out.returncode, out.stderr, out.duration_ms
```

The child side, in the same package so the marker is spelled once:

```python
from any_proc.run import emit, read_args

args = read_args()                      # None when nothing was sent
emit({"status": "success", "result": do(args)})
```

- **Arguments are checked before anything spawns.** A non-object, an unserializable value
  or a payload over `max_args_bytes` raises `ArgsError`; no child runs. `read_args` raises
  it too for stdin that is not a JSON object.
- **The process limit is headroom.** `RLIMIT_NPROC` counts every process (macOS) or thread
  (Linux) of the user, not the child's own, so a fixed total fails any fork on a busy
  machine. The cap is the user's count at spawn plus `process_headroom`; the count is read
  in the parent before the fork. If it cannot be read, the limit is left as inherited.
- **Limits are best-effort where the OS refuses them.** macOS reports `RLIMIT_AS`'s hard cap
  as infinite and refuses a finite one; the spawn goes ahead without it. A limit never
  raises a hard cap.
- **A child's failure is a value.** No result, a non-zero code or a timeout come back in the
  `Outcome`; only bad arguments raise.

## `any_proc.supervise` — keep one child alive

```python
from any_proc.supervise import Health, State, Supervisor, rotate_log

sup = Supervisor(spawn, probe, classify_exit=classify, startup_timeout=300)
sup.start()      # spawn, poll the probe until up, or settle down with a reason
sup.supervise()  # the timer step: read health, respawn a recoverable death
sup.stop()       # SIGTERM, SIGKILL after the wait
sup.state, sup.reason, sup.version, sup.terminal
```

- **A probe answers with `Health`.** `"up"`, `"starting"` and `"down"` are the supervisor's. Any other
  status is terminal: a verdict no respawn changes (a lock another owner holds, a version
  others are attached to). The supervisor stops touching the child and keeps the name in
  `sup.terminal`. `classify_exit(code)` is where an exit becomes terminal.
- **Answering but not ready is `starting`, waited for however long it takes.** `start` returns
  at once on it, and `supervise` neither kills nor respawns it: a server pulling gigabytes of
  models is slow, not dead. `startup_timeout` bounds only the silence before a first answer.
- **Alive but silent is `unresponsive`, never respawned.** A second child next to a live one
  could only fight it for what it holds.
- **Respawns are bounded.** Capped exponential backoff, and at most `restart_budget`
  respawns per `restart_window`; an exhausted budget settles `down` with the count. A
  healthy `up` forgives the past.
- **`start` never raises** and never spawns over a live child.
- `rotate_log(path, keep=2)` rolls `log` to `log.1`, `log.2` before a run opens it fresh.

## cpus

`os.cpu_count()` is the host's: under `cpus: 2` on a 16-core host a thread count taken from it
starts eight threads spin-waiting for two CPUs of quota. `any_proc.cpus` is not about child
processes; it is the host/OS helper that lives here until the package is renamed.

```python
from any_proc.cpus import available_cpus

threads = max(1, available_cpus() // 2)
```

- `host_cpus()` — `len(os.sched_getaffinity(0))` where it exists (Linux); else `os.cpu_count()`
  (macOS, Windows, or a refused call); never below 1.
- `cgroup_quota(cgroup_dir=None)` — cgroup v2 `cpu.max` at the root, else v1
  `cpu.cfs_quota_us` / `cpu.cfs_period_us` in the root, `cpu/` or `cpu,cpuacct/`; rounded up
  (1.5 CPUs is 2). `max`, `-1`, a zero period, garbage or missing files give `None`.
- `Cpus.read(cgroup_dir=None)` — frozen `Cpus(host, quota)`; `.available` is `min(host, quota)`.
- `available_cpus(cgroup_dir=None)` — `Cpus.read(cgroup_dir).available`. The default tree is
  `CGROUP_DIR` (`/sys/fs/cgroup`). Re-read on every call; no cache.
