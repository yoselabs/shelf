# Phase stopwatch

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

- `PhaseClock(now, limits=None, *, root="run", exempt=(), budget=None)`: `now` is a monotonic seconds callable; `limits` maps phase to seconds; `budget` caps `charged()`.
- `phase(name)`: context manager; the innermost open phase owns every instant, the outer one pauses. An exception still closes the phase and books its time.
- Time outside any `phase()` belongs to `root`. Invariant: `sum(totals().values()) == wall()`.
- `current()`, `total(name)` (live while open; 0 if never entered), `totals()`, `wall()`.
- `charged()`: seconds in non-exempt phases. `over()`: `[(phase, spent, limit)]` for limited phases strictly past their limit, then `("charged", spent, budget)` when `charged()` is past `budget`.
- A `now` stepping back books nothing, and nothing is booked twice when it recovers (high-water mark). Single-threaded: `phase()` from a thread other than the creator raises `RuntimeError`.
- The clock cannot stop a caller entering the wrong phase.

No consumer app is imported. Executable acceptance: `tests/`.
