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
| `PhaseClock(now, limits=, root=, exempt=, budget=)` | start the stopwatch; `budget` caps `charged()`; unphased time goes to `root` |
| `phase(name)` | context manager; nests, the inner phase pauses the outer, exceptions close it |
| `book(phase, seconds)` | move seconds you measured yourself out of the innermost open phase into `phase`; capped at what that phase owns, returns what moved |
| `current()` / `wall()` | the owning phase / seconds since start |
| `total(name)` / `totals()` | live seconds per phase |
| `charged()` | seconds in non-exempt phases |
| `over()` | `(phase, spent, limit)` for limited phases past their limit, plus `("charged", spent, budget)` |

```python
clock.book("network", waited)  # waited seconds measured elsewhere; the open phase gives them up, wall() is unchanged
```

Single-threaded by design; another thread calling `phase()` or `book()` raises. Contract: [CONTRACT.md](CONTRACT.md).
