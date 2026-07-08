# timefmt

**Stop hand-formatting durations.** One adaptive formatter so every duration string
in a codebase reads alike — the unit tracks the magnitude, no wasted precision.

```python
from timefmt import fmt_dur

fmt_dur(0)       # "0ms"
fmt_dur(999)     # "999ms"
fmt_dur(1000)    # "1.0s"
fmt_dur(6999)    # "7.0s"
fmt_dur(7000)    # "7s"
fmt_dur(59_999)  # "59s"
fmt_dur(60_000)  # "1m00s"
fmt_dur(125_000) # "2m05s"
```

- **Adaptive** — sub-second stays integer milliseconds; low seconds carry one
  decimal; whole seconds drop it; a minute or more renders `{m}m{ss}s`.
- **Zero-dependency** — integer in, string out.
- **Domain-free** — where a duration appears is the caller's policy, not the
  primitive's.

## Surface

- `fmt_dur(ms: int) -> str`
