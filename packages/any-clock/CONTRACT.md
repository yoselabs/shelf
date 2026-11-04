# Phase stopwatch

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

- `PhaseClock(now, limits=None, *, root="run", exempt=())`: `now` is a monotonic seconds callable; `limits` maps phase to seconds.
- `phase(name)`: context manager; the innermost open phase owns every instant, the outer one pauses. An exception still closes the phase and books its time.
- Time outside any `phase()` belongs to `root`. Invariant: `sum(totals().values()) == wall()`.
- `current()`, `total(name)` (live while open; 0 if never entered), `totals()`, `wall()`.
- `charged()`: seconds in non-exempt phases. `over()`: `[(phase, spent, limit)]` for limited phases strictly past their limit.
- A `now` stepping back books nothing. Single-threaded: `phase()` from a thread other than the creator raises `RuntimeError`.
- The clock cannot stop a caller entering the wrong phase.

No consumer app is imported. Executable acceptance: `tests/`.
