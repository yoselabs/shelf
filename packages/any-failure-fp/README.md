# any-failure-fp

Stop re-writing failure grouping. Normalise a failure reason into a fingerprint, then ask a history of earlier
failures whether this one is a storm, a streak or a repeat, and how long to wait before the retry. Stdlib only.

```python
import re
from any_failure_fp import Event, backoff, fingerprint, head, seen_within, streak, trip

ticket = re.compile(r"\b[a-z]+-\d+\b")
a = fingerprint("build tl-19 failed in /Users/me/x.py after 2.8 s", ids={"ticket": ticket})
b = fingerprint("build tl-77 failed in /home/ci/y.py after 14 s", ids={"ticket": ticket})
assert a == b == "build <ticket> failed in <path> after <n> s"

history = [Event("job-1", a, 100.0), Event("job-2", a, 160.0)]
assert trip(history, "job-3", a, 200.0, window_s=600, min_keys=3).keys == ("job-1", "job-2", "job-3")
assert streak(history, "job-1", a, stop=lambda e: e.kind == "ask") == 2
assert seen_within([Event("job-1", a, 100.0, "fault")], "job-1", "fault", a, now=200.0, window_s=3600)
assert backoff(60, 3600, 2, lambda: 0.5) == 240  # 60 * 2**2, jitter ±20% around it
assert head(fingerprint("x" * 300)) == "x" * 112
```

| call | job |
|---|---|
| `fingerprint(text, ids=, tail=)` | stable slug: ANSI, URLs, paths, sessions, uuids, shas, host ids (`ids`), quotes, braces, numbers replaced by `<label>`; a tail over `tail` chars gets a sha1 suffix |
| `head(fp)` | the slug without that suffix |
| `trip(history, key, fp, now, *, window_s, min_keys, count=)` | `Trip` when `fp` hit `min_keys` distinct keys inside the window |
| `streak(history, key, fp, stop)` | failures with `fp` for `key` since its last `stop` event, counting this one |
| `seen_within(history, key, kind, fp, *, now, window_s)` | the dedupe check for a repeated report |
| `backoff(base, cap, attempt, rand, jitter=0.2)` | capped exponential delay, `rand` injected |

History is a sequence of `Event(key, fp, t, kind)`; the host maps its own rows. Policy (which kinds count, the
windows, the retry caps) stays with the host. Contract: [CONTRACT.md](CONTRACT.md).
