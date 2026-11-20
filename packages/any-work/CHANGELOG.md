# any-work — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new. `Work(db_path, lease_root, *, clock=time.time, rand=random.random, max_attempts=5, backoff_base=30.0, backoff_cap=3600.0)`; `.add(items: Iterable[Item]) -> int` (idempotent, existing keys untouched); `.claim(kind=None) -> Claimed | None`; `.progress() -> Progress`; `.retry_view() -> list[RetryRow]`; `.close()`
- 0.1.0: `Claimed(key, kind, payload, attempts)`: `.finish(failure: Failure | None = None)  # None = ok`, `.release()`, context manager; row written before the flock is released; no `running` status (liveness = any-lease `try_claim` flock)
- 0.1.0: `Failure(kind: Kind, error: str).fp`; `Kind` = transient | permanent | unknown (StrEnum); transient/unknown -> pending with `any_failure_fp.backoff` until `max_attempts`, then quarantined; unknown never permanent; permanent -> permanent; ok -> done
- 0.1.0: `async drain(work, handler, *, concurrency=1, idle_exit_s=30, poll_s=1, kind=None, sleep=asyncio.sleep, clock=time.monotonic)`; handler returns = ok, raises `ClassifiedError(Failure)` = that failure, any other exception = `Failure(UNKNOWN)`
- 0.1.0: table `work(key PK, kind, status, attempts, last_error, fp, next_try_at, priority, payload JSON)`, sqlite-store schema `any-work` v1
- 0.1.0: new `any_work.testing.ManualClock(now=1000.0)`: callable clock, `async sleep(s)` advances it
