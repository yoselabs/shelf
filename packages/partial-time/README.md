# partial-time

**Stop caring what precision a date was written at.** Every time value is the half-open
interval `[lo, hi)` it names, so one comparison serves a year, a month, a day and an instant.

```python
import partial_time as pt

pt.interval("2026")          # (2026-01-01, 2027-01-01)
pt.interval("2026-07")       # (2026-07-01, 2026-08-01)
pt.interval("2026-07-09")    # (2026-07-09, 2026-07-10)
pt.interval("2026-07-09T13:00:00+03:00")  # (10:00:00, 10:00:01) — naive UTC
pt.interval(date(2026, 7, 9))             # the day
pt.interval("July")          # None: not a time
pt.format_interval(lo, hi)   # "2026-07": the precision is the width
```

## Rules

- Equality is overlap: `2026-07` contains every day of July, and a range compares starts.
- Accepted: `date`, `datetime`, `YYYY`, `YYYY-MM`, `YYYY-MM-DD`, an ISO instant with or
  without a zone (a trailing `Z` included). Anything else, `bool` included, is `None`, never
  an exception.
- Bounds are **naive UTC**, microseconds dropped. A zone is converted, then removed: a
  tz-aware value bound into a database can be shifted through the session time zone.
- `format_interval` writes the instant (`…T…Z`), the day, the month or the year, by width.

Stdlib only.
