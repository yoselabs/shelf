# any-lease — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.4.0: new `Pacer.penalize(key, seconds, *, reason="") -> float`: shared `blocked_until = max(existing, now + seconds)`, returns it; state `<root>/<slug>-<hash>.block`, written under the `.pace` flock; `seconds < 0` ⇒ ValueError
- 0.4.0: new `Pacer.blocked_until(key) -> float | None` (None when not blocked or passed), `Pacer.clear(key)`
- 0.4.0: new `Pacer.status(key) -> PaceStatus(next_slot, blocked_until, reason)` (frozen, exported); reads under a shared lock, books no slot, creates no file
- 0.4.0: `wait`/`apace`/`reserve` slot is `max(now, next, blocked_until)`: callers sleep through a block; unchanged when nothing was penalized
- 0.3.2: `python -m any_lease run` hands its command `{**os.environ, ANY_LEASE_HELD}` again (reverses the 0.3.0 child-env note): credentials and agent-session variables (`*TOKEN*`, `*SECRET*`, `AWS_*`, `GH_*`, `CLAUDE_*`, `ANTHROPIC_*`, `MCP_*`) reach the command; a lock around a command must not change it; compatible with 0.3.0 callers; drops dependency `child-env`
- 0.3.0: `python -m any_lease run` handed its command `{**os.environ, ANY_LEASE_HELD}`  ⇒  `child_env.build_env(os.environ, allow=("*",), extra={ANY_LEASE_HELD})`: every variable except credentials (`*TOKEN*`, `*SECRET*`, `AWS_*`, `GH_*`, ...) and agent-session ones (`CLAUDE_*`, `ANTHROPIC_*`, `MCP_*`, ...), which the command no longer inherits
- 0.3.0: the poll between flock attempts waits on a `threading.Event` (the caller's `cancel`, or a private one) instead of `time.sleep`; same wake-up on cancel, no behaviour change
- 0.3.0: `claims/` and `.pace` file names hash through `content_digest.digest_text(key, length=16)`: same names, same bytes (golden-tested)
- 0.3.0: new dependencies `child-env>=0.2,<1`, `content-digest>=0.2,<1`; `process-lock>=0.3`
- 0.2.0: new `Leases.try_claim(key, *, label=None, meta=None) -> Held | None`: one unit per free-form key (slash ok), flock at `<root>/claims/<slug>-<sha256[:16]>.lock`, no `.limit`, never waits, None when held (same process too); lock file kept after release; `Held.name=key, slot=0`
- 0.2.0: new `Pacer(root, *, clock=time.time, sleep=time.sleep, asleep=asyncio.sleep)`; `.wait(key, every) -> float` and `async .apace(key, every) -> float` block until ≥`every` s after the last pass on `key` by any process, return the reserved slot (wall time); `.reserve(key, every) -> float` books the next slot without sleeping (a queue's `next_try_at`); no retry/backoff; state `<root>/<slug>-<hash>.pace`; slots reserved under flock, sleep outside it
- 0.1.0: new. `Leases(root).acquire(name, limit, *, timeout=None, cancel=None, label=None, on_wait=None, poll=0.5) -> Held(name, slot, waited)`; `acquire_all(wants, ...) -> HeldAll(held, waited)` in sorted name order; `holders(name, limit) -> tuple[Occupant, ...]`; errors `LeaseTimeoutError`, `LeaseCancelledError`
- 0.1.0: `acquire`/`acquire_all` take `meta=None`, merged into the holder record under `{name, slot}`
- 0.1.0: `limit` optional after a first call declares it in `<root>/<name>.limit`; new `Leases.declare(name, limit=None) -> int`; mismatch ⇒ ValueError; `acquire_all` takes bare names
- 0.1.0: `holders(name, limit=None)` counts a unit only while its flock is held (probe); `Occupant.holder` may be None
- 0.1.0: new `python -m any_lease run [--root R] NAME LIMIT LABEL -- cmd` (signals forwarded, `ANY_LEASE_HELD` nesting, `ANY_LEASE_ROOT`)
- 0.3.1: takes its lock with `ProcessLock.acquire_exclusive` (process-lock 0.4.0); requires `process-lock>=0.4,<1`; no behaviour change
