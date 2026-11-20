# any-lease — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.2.0: new `Leases.try_claim(key, *, label=None, meta=None) -> Held | None`: one unit per free-form key (slash ok), flock at `<root>/claims/<slug>-<sha256[:16]>.lock`, no `.limit`, never waits, None when held (same process too); lock file kept after release; `Held.name=key, slot=0`
- 0.2.0: new `Pacer(root, *, clock=time.time, sleep=time.sleep, asleep=asyncio.sleep)`; `.wait(key, every) -> float` and `async .apace(key, every) -> float` block until ≥`every` s after the last pass on `key` by any process, return the reserved slot (wall time); `.reserve(key, every) -> float` books the next slot without sleeping (a queue's `next_try_at`); no retry/backoff; state `<root>/<slug>-<hash>.pace`; slots reserved under flock, sleep outside it
- 0.1.0: new. `Leases(root).acquire(name, limit, *, timeout=None, cancel=None, label=None, on_wait=None, poll=0.5) -> Held(name, slot, waited)`; `acquire_all(wants, ...) -> HeldAll(held, waited)` in sorted name order; `holders(name, limit) -> tuple[Occupant, ...]`; errors `LeaseTimeoutError`, `LeaseCancelledError`
- 0.1.0: `acquire`/`acquire_all` take `meta=None`, merged into the holder record under `{name, slot}`
- 0.1.0: `limit` optional after a first call declares it in `<root>/<name>.limit`; new `Leases.declare(name, limit=None) -> int`; mismatch ⇒ ValueError; `acquire_all` takes bare names
- 0.1.0: `holders(name, limit=None)` counts a unit only while its flock is held (probe); `Occupant.holder` may be None
- 0.1.0: new `python -m any_lease run [--root R] NAME LIMIT LABEL -- cmd` (signals forwarded, `ANY_LEASE_HELD` nesting, `ANY_LEASE_ROOT`)
