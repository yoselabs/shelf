# Phase stopwatch

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

- `PhaseClock(now, limits=None, *, root="run", exempt=(), budget=None, elapsed=0.0)`: `now` is a monotonic seconds callable; `limits` maps phase to seconds; `budget` caps `charged()`; `elapsed` is seconds the clock has already run, all owned by `root` (negative, NaN or infinite raises `ValueError`). `wall()` includes it. `started` = the construction `now()` reading minus `elapsed`.
- `phase(name)`: context manager; the innermost open phase owns every instant, the outer one pauses. An exception still closes the phase and books its time.
- Time outside any `phase()` belongs to `root`. Invariant: `sum(totals().values()) == wall()` (within float rounding).
- `book(phase, seconds) -> float`: move already-measured seconds from the innermost open phase at call time (the donor, `current()`) into `phase`; returns what moved. Capped at the donor's total (no total goes negative); `seconds` <= 0 or NaN moves 0; booking into the donor itself moves 0. Keeps `sum(totals().values()) == wall()` (within float rounding); a booked exempt phase lowers `charged()`.
- `current()`, `total(name)` (live while open; 0 if never entered), `totals()`, `wall()`.
- `charged()`: seconds in non-exempt phases. `over()`: `[(phase, spent, limit)]` for limited phases strictly past their limit, then `("charged", spent, budget)` when `charged()` is past `budget`.
- A `now` stepping back books nothing, and nothing is booked twice when it recovers (high-water mark).
- Thread-safe: one lock guards all state; no time is lost or double counted under concurrent calls, so `sum(totals().values()) == wall()` (within float rounding) holds. The phase stack is shared by every thread: `phase()` from two threads at once nests in arrival order, a phase exit pops the innermost open phase (whichever thread leaves), and `book()`'s donor is the innermost open phase at call time. `now` is called under the lock and must not call back into the clock.
- Restore: `PhaseClock(now, elapsed=e)` then `book("wait", w)` moves `min(w, e)` out of `root`.
- The clock cannot stop a caller entering the wrong phase.

No consumer app is imported. Executable acceptance: `tests/`.
