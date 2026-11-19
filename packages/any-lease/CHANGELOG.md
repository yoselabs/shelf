# any-lease — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new. `Leases(root).acquire(name, limit, *, timeout=None, cancel=None, label=None, on_wait=None, poll=0.5) -> Held(name, slot, waited)`; `acquire_all(wants, ...) -> HeldAll(held, waited)` in sorted name order; `holders(name, limit) -> tuple[Occupant, ...]`; errors `LeaseTimeoutError`, `LeaseCancelledError`
- 0.1.0: `acquire`/`acquire_all` take `meta=None`, merged into the holder record under `{name, slot}`
- 0.1.0: `limit` optional after a first call declares it in `<root>/<name>.limit`; new `Leases.declare(name, limit=None) -> int`; mismatch ⇒ ValueError; `acquire_all` takes bare names
- 0.1.0: `holders(name, limit=None)` counts a unit only while its flock is held (probe); `Occupant.holder` may be None
- 0.1.0: new `python -m any_lease run [--root R] NAME LIMIT LABEL -- cmd` (signals forwarded, `ANY_LEASE_HELD` nesting, `ANY_LEASE_ROOT`)
- 0.2.0: `python -m any_lease run` handed its command `{**os.environ, ANY_LEASE_HELD}`  ⇒  `child_env.build_env(os.environ, allow=("*",), extra={ANY_LEASE_HELD})`: every variable except credentials (`*TOKEN*`, `*SECRET*`, `AWS_*`, `GH_*`, ...) and agent-session ones (`CLAUDE_*`, `ANTHROPIC_*`, `MCP_*`, ...), which the command no longer inherits
- 0.2.0: the poll between flock attempts waits on a `threading.Event` (the caller's `cancel`, or a private one) instead of `time.sleep`; same wake-up on cancel, no behaviour change
- 0.2.0: new dependency `child-env>=0.2,<1`; `process-lock>=0.3`
