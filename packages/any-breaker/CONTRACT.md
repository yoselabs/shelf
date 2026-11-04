# Fold-based circuit breaker

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

`Breaker(policy).fold(facts, state=None) -> State` is pure: no clock, no I/O, the checkpoint untouched.
`fold(tail, fold(head)) == fold(all)` for time-ordered facts. `view(state, key, t) -> View` answers
whether `key` may launch at `t`; after a bench or out ends the view is closed with `canary=True`.
`Policy(n, window_s, distinct, ladder_s, rules, outs)` is the whole configuration; an empty ladder raises
`ValueError`. `Ledger(breaker, path).record/allow` persists facts as JSON lines and takes the time as an
argument. `Guard(ledger, key, call, judge)` raises `BreakerOpenError` while the key is benched and records the
outcome `judge` returns. No consumer app is imported; nothing outside the standard library.

Executable acceptance: `tests/test_golden_delegate.py` (delegate's incident replays, row by row),
`tests/test_breaker.py` (thresholds, ladder, canary, outs, checkpoint equality), `tests/test_ledger.py`,
`tests/test_guard.py`, and `tests/test_boundary_any_breaker.py` (consumer and stdlib boundary).
