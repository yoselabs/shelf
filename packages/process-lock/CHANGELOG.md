# process-lock — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.2.0: `acquire(path)` only  ⇒  `acquire(path, *, timeout=0.0, on_wait=None, label=None, meta=None, reentrant=True)`; `timeout` seconds to wait (None: forever), `on_wait(Waiting(path, elapsed, holder))` per poll, expiry ⇒ `LockHeldError`
- 0.2.0: lock-file body bare pid  ⇒  JSON `{pid, created, label, meta}`; new `holder(path) -> Holder | None` reads it without the lock (bare-pid files still parse)
- 0.2.0: `reentrant=False` ⇒ a second acquire of the path in the same process waits or raises `LockHeldError` (pid = own); re-entry needs both acquirers reentrant
- 0.2.0: `LockHeldError(path, pid)`  ⇒  `LockHeldError(path, pid, holder=None)`; new exports `Holder`, `Waiting`, `holder`
- 0.2.0: tests: `test_held_names_what_this_process_holds` asserted the file body is the bare pid  ⇒  asserts `holder(path).pid`
- 0.2.0: a held lock is never broken; timeout while the recorded pid is dead ⇒ `LockHeldError` text "held by an inherited descriptor; recorded holder pid N is gone" (`.path/.pid/.holder` kept); no subprocess, no /proc
