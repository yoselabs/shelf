# any-lease

**Stop hand-rolling "at most N at a time, across processes".** A named resource has `limit` units; a
caller holds one while it works and queues when all are taken. Each unit is a
[process-lock](../process-lock/README.md) flock, so the kernel frees it when its holder dies
(`kill -9` included): no stale lease, no pid to trust. A hold ends only on release or holder death: no expiry, no TTL.
POSIX only (macOS, Linux). Requires `process-lock` (the flock core is reused, not copied), which is itself stdlib-only;
there is no other dependency, and a vendoring consumer copies both packages.

```python
from pathlib import Path
from threading import Event
from any_lease import Leases

leases = Leases(Path("~/.app/leases").expanduser())      # one folder is one table

with leases.acquire("unity", 1, timeout=600, label="bead-7:build") as held:
    print(held.slot, held.waited)                         # which unit, seconds queued

cancel = Event()                                          # set from another thread to stop queuing
leases.acquire("dotnet", 2, cancel=cancel, on_wait=lambda w: print(w.elapsed, w.occupants))

with leases.acquire_all({"unity": 1, "dotnet": 2}) as got:   # name order, whatever the listing
    print([h.name for h in got.held], got.waited)

leases.holders("unity")          # (Occupant(slot, Holder),) -- the units taken now
leases.declare("unity", 1)       # the limit is kept in <root>/unity.limit; later calls may omit it
```

```bash
# hold a unit for a command (signals forwarded, exit code returned); nested runs of the same name just run
python -m any_lease run --root ~/.cache/app/leases unity 1 "bead-7:build" -- ./build.sh   # or ANY_LEASE_ROOT
```

## Rules

- **Counting.** `acquire(name, limit)` tries units `0..limit-1` in order (`<root>/<name>-<slot>.lock`),
  non-blocking, then polls every `poll` seconds (default 0.5).
- **One declared limit.** The first caller that gives a `limit` writes `<root>/<name>.limit` (atomically; racing first
  callers agree on one winner). After that `limit` may be omitted, and a different one raises `ValueError`, in
  `acquire`, `acquire_all` and `holders` alike. An omitted limit on a never-declared name is a `ValueError`. To change a limit, delete the
  file while nothing holds the name.
- **`python -m any_lease run NAME LIMIT LABEL -- cmd...`** holds a unit for the command's lifetime (`--root` or
  `$ANY_LEASE_ROOT`). SIGINT and SIGTERM go to the command; its exit code is returned (128+n when a signal ended it).
  The command sees `ANY_LEASE_HELD=<names>`: a nested `run` of a name already held by an ancestor runs without taking a
  second unit. It prints once to stderr who it waits for.
- **Ending a wait.** `timeout` (seconds; 0 = try once; None = forever) raises `LeaseTimeoutError(name, limit, occupants)`;
  `cancel` set raises `LeaseCancelledError(name)` and wakes the wait at once. An exception from `on_wait` also ends it.
  Nothing is held after any of them.
- **`acquire_all`** takes one unit of each `(name, limit)` in sorted name order, so two callers listing the same
  names differently cannot wait on each other. `timeout` covers the whole set; a failure part way frees what was
  won. `HeldAll.waited` is the sum.
- **`holders`** reports a unit as taken only while its flock is held, found by a shared flock probe on a separate descriptor, dropped
  at once (a record left behind by a released unit never counts). The probe can make a `timeout=0` acquirer miss that
  unit in the same instant; waiters retry on their next poll. Each `Occupant.holder` is the record the holder wrote
  (`None` for a holder that has not written one yet).
- **Threads.** Units are taken with `process_lock`'s `reentrant=False`, which refuses a second acquire of one
  path inside a process, so threads of one process exclude each other without a mutex of this package's own.
- **Holder record.** `label` and `meta` land in the unit's lock file (JSON, readable while the unit is held); a
  waiter sees them in `Waiting.occupants` and `LeaseTimeoutError.occupants`. Host-global: any process, any worktree,
  one `root` folder. macOS and Linux; no Windows (process-lock is `fcntl`).
- **Names** match `[A-Za-z0-9_][A-Za-z0-9_.-]*`; `limit >= 1`; otherwise `ValueError`.
- Release is idempotent; `Held` and `HeldAll` are context managers. The descriptor is not inherited across `exec` (PEP 446), so a spawned command does not keep the unit. A raw `os.fork()`
  without exec does: the child keeps the unit after the holder dies, until the child exits (tested).
