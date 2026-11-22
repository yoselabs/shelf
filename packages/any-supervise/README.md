# any-supervise

**Stop hand-tracking long-lived worker processes.** A TOML spec lists the workers; one state file per replica records its pid
and its process start time, so the supervisor starts them detached, tells you which run old code, restarts them one at a time
and stops only what is provably its own. POSIX only (macOS, Linux). Born `candidate`.

Default view: `status` returns one row per replica, `running` / `stale` / `dead` / `missing` / `orphan`, with the code version it
started on and the one `version_cmd` prints now.
Opt-ins: none. `roll` takes `parallel` and `names`; `up`, `status`, `down` and `logs` take no options.

```toml
# fleet.toml
state = "state"                                  # folder of the per-replica JSON files
version_cmd = ["git", "rev-parse", "HEAD"]       # stdout, stripped, is the code version
version_cwd = "~/Workspaces/channel-research"

[[worker]]
name = "snapshots"
command = ["uv", "run", "--script", "batch.py", "snapshots", "--shard", "{index}/{count}"]
count = 4                                        # replicas snapshots-1 .. snapshots-4
cwd = "~/Workspaces/channel-research"
log = "logs"                                     # logs/snapshots-1.log ...
stop_timeout_s = 60
env = { BATCH_MODE = "prod" }               # set in every replica
env_pass = ["UV_*", "OPENAI_API_KEY"]        # names or PREFIX* patterns taken from the launcher's environment
```

```bash
any-supervise up fleet.toml              # start every missing replica, detached; idempotent
any-supervise status fleet.toml --json   # exit 1 if anything is stale, dead, missing or orphaned
any-supervise roll fleet.toml            # restart the stale replicas, one lane member at a time
any-supervise roll fleet.toml snapshots-2 --parallel 2   # restart these even if current
any-supervise down fleet.toml [NAME]     # graceful stop, state file removed
any-supervise logs fleet.toml snapshots-2 -n 100
```

```python
import os
from pathlib import Path
from any_supervise import Host, load_spec, roll, status, up

spec = load_spec(Path("fleet.toml"))
host = Host(environ=os.environ)          # the edge supplies the launcher's environment; clock= and sleep= are injectable
for row in status(spec, host):           # ReplicaStatus(name, state, pid, version, current, started_at)
    print(row.name, row.state)
```

## Contract

| rule | behaviour |
|---|---|
| Identity | A replica is ours only while its state file's `pid` is alive AND its process start time equals the recorded one (`stream_proc.alive`). Anything else is not ours and is never signalled: a recycled pid, a process with no state file, a state file that does not parse (`StateError`). |
| Detach | `up` starts a replica in a session of its own, stdin `/dev/null`, stdout and stderr appended to `<log>/<replica>.log`, no inherited descriptor: the launcher returns at once and a caller reading its pipes sees EOF. |
| Idempotent `up` | Starts replicas that are missing or dead; a live one (stale or not) is left alone. A dead replica's state file is overwritten. |
| Stale | `status` runs `version_cmd` (30 s limit) and compares its stdout with the version recorded at start: different is `stale`. The worker is never asked. A failing or empty `version_cmd` raises `VersionProbeError`; it never reads as "all stale". |
| `status` states | `running` (alive, current), `stale` (alive, old version), `dead` (state file, no matching process), `missing` (in the spec, no state file), `orphan` (alive, state file, not in the spec). The CLI exits 1 unless every row is `running`. |
| `roll` | Targets the stale replicas, or those `names` select (a worker's all, or one replica) whether stale or not. Per replica: identity check, SIGTERM to its process tree, wait `stop_timeout_s`, SIGKILL, start the replacement on the current version, require it alive for `settle_s` (3 s), then the next. A replacement that dies in that window raises `ReplacementDiedError` and stops the roll; later replicas are untouched. A survivor of SIGKILL raises `StopFailedError`. |
| Lanes | At most `parallel` replicas in flight, and at most `count - 1` of one worker (min 1) at once, so a lane with `count > 1` never drops to zero. Before a lane's first stop, its dead or missing replicas (not among the targets) are started, so the live count never starts below the lane's size. A worker with `count = 1` is down between its stop and its replacement; nothing can avoid that. |
| `down` | Stops what is ours (all state files, one worker, one replica, or an orphan by name) with the same SIGTERM, timeout, SIGKILL, then removes its state file. A state file whose process is already gone is just removed. Every target is attempted; several failures raise one `ExceptionGroup`. |
| One writer | `up`, `roll`, `down` hold `<state>/.lock`; a second raises `BusyError` at once. `status` and `logs` take no lock. |
| Env | A worker gets an allowlist, never the launcher's whole environment ([child-env](../child-env/README.md) `build_env`): `PATH`, `HOME`, `USER`, `LANG`, `LC_*`, `TERM`, `TMPDIR`, `TZ`, `XDG_*` and the like, plus the names in `env_pass` (exact, or `PREFIX*`; a secret-looking name passes only by its exact name), plus `env`, plus `ANY_SUPERVISE_INDEX` (1-based) and `ANY_SUPERVISE_COUNT`. `version_cmd` gets the default allowlist only. |
| Argv | `{index}` and `{count}` inside a `command` item are replaced per replica; the recorded `argv` is the resolved one. |
| Names | A worker name is `[A-Za-z0-9][A-Za-z0-9_.-]*`; worker and replica names (`<worker>-<n>`) must all differ. |
| Pattern kills | There is no kill by name or pattern, and none can be added: the only way to a signal is a state file whose identity still matches. |

Limits: the identity check and the signal are two steps (see [stream-proc](../stream-proc/README.md): a pid reused in that gap can
still be hit). The supervisor does not restart a worker that dies by itself; it reports `dead`, and a timer or the owner runs `up`.
Single host. The log grows without rotation.

Built on [stream-proc](../stream-proc/README.md) (`spawn_detached`, `stop_pid`, `alive`, `capture`),
[process-lock](../process-lock/README.md), [atomic-io](../atomic-io/README.md) and [child-env](../child-env/README.md).
`any_supervise.testing.ManualClock` is a clock and `sleep` the test moves by hand.
