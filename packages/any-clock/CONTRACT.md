# Phase stopwatch

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

- `PhaseClock(now, limits=None, *, root="run", exempt=(), budget=None)`: `now` is a monotonic seconds callable; `limits` maps phase to seconds; `budget` caps `charged()`.
- `phase(name)`: context manager; the innermost open phase owns every instant, the outer one pauses. An exception still closes the phase and books its time.
- Time outside any `phase()` belongs to `root`. Invariant: `sum(totals().values()) == wall()`.
- `book(phase, seconds) -> float`: move already-measured seconds from the innermost open phase at call time (the donor, `current()`) into `phase`; returns what moved. Capped at the donor's total (no total goes negative); `seconds` <= 0 or NaN moves 0; booking into the donor itself moves 0. Keeps `sum(totals().values()) == wall()`; a booked exempt phase lowers `charged()`.
- `current()`, `total(name)` (live while open; 0 if never entered), `totals()`, `wall()`.
- `charged()`: seconds in non-exempt phases. `over()`: `[(phase, spent, limit)]` for limited phases strictly past their limit, then `("charged", spent, budget)` when `charged()` is past `budget`.
- A `now` stepping back books nothing, and nothing is booked twice when it recovers (high-water mark). Single-threaded: `phase()` or `book()` from a thread other than the creator raises `RuntimeError`.
- The clock cannot stop a caller entering the wrong phase.

No consumer app is imported. Executable acceptance: `tests/`.
