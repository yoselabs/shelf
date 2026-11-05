# Changelog

## 0.3.0

- Thread-safe: one lock around all state. The "another thread raises `RuntimeError`" rule is gone. The phase stack is
  shared by every thread (concurrent `phase()` nests in arrival order; `book()`'s donor is the innermost open phase at
  call time); totals still add up to `wall()` under concurrent calls.
- `PhaseClock(..., elapsed=0.0)`: start part-way through, the elapsed seconds owned by `root`; `started` property: the
  back-dated start reading. For a host restoring a run after a re-exec (task-loop `Budget` reload).

## 0.2.0

- `book(phase, seconds) -> float`: move already-measured seconds from the innermost open phase into `phase`, capped at
  what the donor owns; the totals still add up to `wall()`. For hosts that time a wait after the fact (task-loop `Budget.wait`).

## 0.1.0

- `PhaseClock`: nested phases, per-phase totals, limits, exempt phases and a budget.
