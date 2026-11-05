# any-clock

Stop attributing time by hand. A nested phase stopwatch: the innermost open phase owns each instant, so time
cannot go unowned, and per-phase totals always add up to wall time. Stdlib only.

```python
from any_clock import PhaseClock

clock = PhaseClock(time.monotonic, {"review": 600}, exempt={"lane", "network"}, budget=10800)
with clock.phase("review"):
    with clock.phase("push"):  # review pauses while this runs
        ...
clock.totals()   # {"run": ..., "review": ..., "push": ...}
clock.charged()  # seconds outside the exempt phases: the budget spent
clock.over()     # [("review", spent, 600)] once past its limit; ("charged", spent, 10800) past the budget
```

| call | job |
|---|---|
| `PhaseClock(now, limits=, root=, exempt=, budget=, elapsed=)` | start the stopwatch; `budget` caps `charged()`; unphased time goes to `root`; `elapsed` starts it part-way (seconds already run, all in `root`) |
| `started` | the `now()` reading the clock counts from: construction reading minus `elapsed` |
| `phase(name)` | context manager; nests, the inner phase pauses the outer, exceptions close it |
| `book(phase, seconds)` | move seconds you measured yourself out of the innermost open phase into `phase`; capped at what that phase owns, returns what moved |
| `current()` / `wall()` | the owning phase / seconds since start |
| `total(name)` / `totals()` | live seconds per phase |
| `charged()` | seconds in non-exempt phases |
| `over()` | `(phase, spent, limit)` for limited phases past their limit, plus `("charged", spent, budget)` |

```python
clock.book("network", waited)  # waited seconds measured elsewhere; the open phase gives them up, wall() is unchanged
```

Restore after a restart: the host stored how long the run had gone and how much of it was waiting.

```python
clock = PhaseClock(time.time, exempt={"wait"}, budget=10800, elapsed=elapsed)  # started == time.time() - elapsed
clock.book("wait", waited)  # capped at elapsed, moved out of root
```

Thread-safe: one lock guards all state, so `book()` from many threads (check lanes) is safe and `sum(totals().values()) == wall()` (within float rounding) holds throughout. The phase stack is shared by every thread, not per thread: `phase()` from two threads at once nests in arrival order, an exit pops the innermost open phase, and `book()`'s donor is the innermost open phase at call time. Contract: [CONTRACT.md](CONTRACT.md).
