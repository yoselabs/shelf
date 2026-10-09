# due-schedule

**Stop caring whether a recurring job is due.** One call over a schedule string, the job's
last run and the time now.

```python
from due_schedule import schedule_is_due, parse_interval, is_valid_cron

schedule_is_due("15m", last_run_at, now)        # interval: due once 15 minutes have passed
schedule_is_due("0 3 * * *", last_run_at, now)  # cron: due once a 03:00 has passed since the last run
parse_interval("6h")                            # timedelta(hours=6); None for anything else
is_valid_cron("*/15 * * * *")                   # True
```

## Rules

- **Interval**: a positive integer and one of `s m h d` (`30s`, `15m`, `6h`, `1d`),
  surrounding whitespace allowed. Never run: due at once. Then due once the interval has
  elapsed since the last run.
- **Cron**: a 5-field expression, read by `croniter`. Never run: due at the **next** fire,
  measured from now; a job discovered at 14:00 with `0 3 * * *` does not fire for the 03:00
  already past. Then due once a fire has passed since the last run.
- **No schedule, or one that is neither** (`""`, `None`, `garbage`, `99x`, a bad cron): never
  due. Logged at debug, never raised — one bad job file does not stop a scheduler's loop.
  Validate up front with `parse_interval` / `is_valid_cron` if you want to refuse it.
- `last_run_at` and `now` must agree on timezone awareness.
