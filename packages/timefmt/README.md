# timefmt

**Stop hand-formatting durations, waits and counts.** Adaptive formatters so every such
string in a codebase reads alike — the unit tracks the magnitude, no wasted precision.

```python
from timefmt import fmt_dur, fmt_span, fmt_until, human_count

fmt_dur(0)       # "0ms"
fmt_dur(999)     # "999ms"
fmt_dur(1000)    # "1.0s"
fmt_dur(6999)    # "7.0s"
fmt_dur(7000)    # "7s"
fmt_dur(59_999)  # "59s"
fmt_dur(60_000)  # "1m00s"
fmt_dur(125_000) # "2m05s"

fmt_span(720)        # "12m"      seconds in; d/h/m, seconds dropped, negative reads as 0
fmt_span(11_220)     # "3h07m"
fmt_span(191_000)    # "2d5h"
fmt_until(t)         # fmt_span(t - time.time()), or "now" once t is not ahead
fmt_until(t, now=n)  # the same against a clock you pass

human_count(950)         # "950"
human_count(12_400)      # "12k"
human_count(1_500_000)   # "1.5M"
```

- **Adaptive** — sub-second stays integer milliseconds; low seconds carry one
  decimal; whole seconds drop it; a minute or more renders `{m}m{ss}s`.
- **Zero-dependency** — integer in, string out.
- **Domain-free** — where a duration appears is the caller's policy, not the
  primitive's.

## Surface

- `fmt_dur(ms: int) -> str`
- `fmt_span(seconds: float) -> str`
- `fmt_until(when: float, *, now: float | None = None) -> str`
- `human_count(n: float) -> str`
