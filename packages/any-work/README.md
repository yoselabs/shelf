# any-work

**Stop hand-rolling "which keys are left, which failed, which to retry" for a long job.** One SQLite table holds a row per
key (`key, kind, status, attempts, last_error, fp, next_try_at, priority, payload`); who is working a key right now is a
per-key [any-lease](../any-lease/README.md) flock, so a worker that dies (`kill -9` included) frees its key at once.
Status is `pending`, `done`, `permanent` or `quarantined`. There is **no `running` status**: a stored "running" outlives its
process, a flock does not. "Done" is a count over rows, never a process exit or a marker file.

Single host, many processes. POSIX only (flock, WAL SQLite on a local disk). Born `candidate`.
Built on [sqlite-store](../sqlite-store/README.md) (WAL, busy timeout 5 s, short `BEGIN IMMEDIATE` transactions),
any-lease >= 0.2 (`try_claim`) and [any-failure-fp](../any-failure-fp/README.md) (`fingerprint`, `backoff`).
It does not import any-pipeline.

```python
import asyncio
from pathlib import Path
from any_work import ClassifiedError, Claimed, Failure, Item, Kind, Work, drain

work = Work(Path("crawl/work.db"), Path("crawl/leases"))      # clock=, rand=, max_attempts=5, backoff_base=30, backoff_cap=3600
work.add([Item("UCabc", kind="channel", payload={"url": "..."}), Item("vid1", kind="video", priority=1)])   # new keys only

async def handler(c: Claimed) -> None:
    result = await fetch(c.key, c.payload)          # handlers COMMIT their result here, before returning
    if result.removed:
        raise ClassifiedError(Failure(Kind.PERMANENT, "video removed"))
    if result.throttled:
        raise ClassifiedError(Failure(Kind.TRANSIENT, "429"))

asyncio.run(drain(work, handler, concurrency=4, idle_exit_s=30))   # claim, run, finish by result, exit when quiet
print(work.progress())      # Progress(by_status={...}, by_kind={...}); .done, .total
print(work.retry_view())    # pending rows with attempts > 0: key, kind, attempts, last_error, next_try_at
```

Without `drain`: `c = work.claim(kind=None)` returns a `Claimed` (`key`, `kind`, `payload`, `attempts`) or None;
`c.finish()` is ok, `c.finish(Failure(kind, error))` is a failure. `any_work.testing.ManualClock` is a clock and `sleep` the test moves by hand. Leaving a `with c:` block without finishing keeps the row pending.

## Contract

| rule | behaviour |
|---|---|
| `add(items)` | Idempotent: an existing key is untouched (payload, kind, status, priority); returns the count added. A feeder calls `enqueue`, not `add`. |
| `enqueue(items, *, bump=False)` | One transaction: inserts new keys, leaves existing ones as they are (with `bump=True`, an existing `pending` row moves to the item's priority when that is more urgent). Returns `Enqueued(new, existing, bumped, states)`, `states` = the given keys counted by final status, read in the same transaction. |
| `bump(keys, priority=0)` | Sets `priority` on `pending` rows whose priority is numerically greater; never touches `done`, `permanent`, `quarantined` or a more urgent row. Returns the count moved. |
| `claim(kind=None)` | The next row with `status = pending` and `next_try_at <= now`, ordered `priority, next_try_at, rowid`, whose `try_claim` succeeds; the row is re-read under the flock, so one finished a moment ago is never handed out. |
| `finish(ok)` | `done`. |
| `finish(Failure(TRANSIENT))` | `attempts + 1`, `pending`, `next_try_at = now + backoff(base, cap, attempts_before, rand)`; the `max_attempts`-th failure makes it `quarantined`. |
| `finish(Failure(UNKNOWN))` | Treated as transient, to the same cap, then `quarantined`. **Never `permanent`.** |
| `finish(Failure(PERMANENT))` | `permanent`, never claimed again. |
| `Failure.fp` | `any_failure_fp.fingerprint(error)`, stored beside `last_error` so a storm is one `GROUP BY fp`. |
| `Kind` | A `StrEnum`: consume it with an exhaustive `match` and `typing.assert_never`; the type checker then flags a missed case. |
| `drain(...)` | `concurrency` workers claim, run the handler, finish by what it did: returns = ok; `ClassifiedError(Failure)` = that failure; any other exception = `Failure(UNKNOWN, "Type: message")`. It stops after `idle_exit_s` with nothing claimable. A row whose retry lies further ahead than that is left for the next drain. `sleep` and `clock` are injectable. |
| `progress()` / `retry_view()` | Queries over the table; velocity, ETA and dry-run are queries to write on it, not features here. |

Deliberately absent: priorities beyond one column, dependencies between items, cron, watchers, sources, dashboards, a broker.
A source (what yields keys) is a consumer callable that feeds `enqueue`. The cap is `add`, `enqueue`, `bump`, `claim`, `finish`, `progress`, `drain`.

A feeder returns `Enqueued` and prints it; never report an enqueue from a file or from intent. Work fed while a worker is busy
(rows due, a claim held) is claimable by the next `claim` once it is `pending` and, with `bump=True`, at the item's priority: the table need not run dry first.

## Two truths: the table and the result store

The table says what was *attempted and how it ended*; the result store (any-pipeline's `Store`, a directory of files) holds
*what came out*. They can disagree if a handler records "ok" before its result is durable. Rules:

- **A handler commits its result, then returns ok.** `finish` runs after the handler returns, so a crash in between leaves the row
  `pending` with its result already stored: the retry finds it and is a cheap no-op, never a loss.
- **`claim` skips nothing based on results.** The table alone decides what is claimable; a handler that sees its result already
  stored returns ok at once. There is one place that says "done", and it is the row.
- A result with no row, or a `done` row with no result, is a bug in the handler, not something this package reconciles.

Glue with any-pipeline (in the consumer, not here): the handler runs the Flow for `c.key` and stores each stage's output through the
pipeline's Store before returning; any-pipeline stays stateless and never learns of statuses.

## Limits

- **Single host.** The flock is per machine and SQLite is on one local disk; NFS and other hosts are out of scope (sqlite-store refuses network filesystems).
- **Contention.** Each write is one short `BEGIN IMMEDIATE` transaction with a 5 s busy timeout. Ten processes draining 200 rows
  are tested; hundreds of processes are not.
- **Wall time.** `next_try_at` is `time.time()` so processes agree; a clock jump moves retries by that jump.
- **A claim is not a lease on time.** A holder that hangs keeps its key; the consumer bounds handler runtime.
- **Same process.** A second `claim` of a key this process already holds returns None, so `concurrency` workers in one process never share a key.
