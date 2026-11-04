# any-breaker

Stop re-writing the circuit breaker. A pure fold of facts into a state, a ledger that replays it from a file, and a guard that turns a call's outcome into a counted fact. Stdlib only, no clock: every time is passed in.

```python
from pathlib import Path
from any_breaker import Breaker, Fact, Guard, Ledger, Out, Policy, Rule, OK

policy = Policy(
    n=3, window_s=600, ladder_s=(900, 1800, 3600),         # 3 same failures in 10 min -> bench 15, then 30, then 60 min
    rules={"server_error": Rule(distinct=2)},                # ...from 2 different sources
    outs={"rate_limited": Out(wait_s=900)},                  # a kind that puts the key out at once
)
breaker = Breaker(policy)

state = breaker.fold([Fact("server_error", 1000, "grok|m", source="t1"),
                      Fact("server_error", 1060, "grok|m", source="t2"),
                      Fact("server_error", 1120, "grok|m", source="t2")])
view = breaker.view(state, "grok|m", now=1121)   # View(state="open", usable=False, until=2020, rung=1, ...)

ledger = Ledger(breaker, Path("breaker.jsonl"))
ledger.record(Fact(OK, now, "grok|m"))
ledger.allow("grok|m", now)                       # -> View

guard = Guard(ledger, "api.example.com", fetch, judge=lambda result, error: "blocked" if result and result.status == 429 else OK)
await guard(url)                                  # BreakerOpenError while benched; a bad *result* counts, not only a raise
```

## Rules

- A `Fact` is `(kind, ts, key)` plus `fp` (what makes two failures the same), `source` (who suffered it), `until` (a vendor's unlock time), `note`. The consumer turns its own rows into facts; a row that is no fact is not passed.
- `OK` ends an out and resets the key's ladder. `RELEASE` forgets the key (every key starting with it when `prefix=True`). A kind in `Policy.outs` puts the key out until `fact.until` if later than the fact, else `ts + wait_s`. Any other kind is a counted failure.
- `n` failures of one kind and one fingerprint inside `window_s`, from `distinct` different sources, open the key for the next rung of `ladder_s`. `Rule` overrides `n`, `window_s`, `distinct` per kind. The last rung repeats.
- A failure that started before the bench began does not count again. The first launch after a bench ends is the canary (`View.canary`): `OK` resets the ladder, a failure starts the next rung at once.
- `fold(facts, state)` never touches `state`, skips facts at or before `state.ts` and sorts the batch by time, so `fold(tail, fold(head)) == fold(all)`; `State.to_dict`/`from_dict` carry it through JSON.
- `Ledger` appends one JSON line per fact and folds only the unread tail on each call; a torn last line waits, a bad line is skipped, a shrunk file is re-read from the start. A fact older than the folded state is ignored, as with a checkpoint.
- `Guard.judge(result, error)` returns a failure kind, `OK`, or `None` (not counted). The error is re-raised after it is recorded.

## What it does not do

No lane or model naming, no failure-text matching or fingerprinting, no usage windows, holds or leases, no HTTP. A key is an opaque string; two levels (a lane and a lane+model) are two keys, a `prefix` release and two views. No metrics, no half-open concurrency limit (the canary is advisory: concurrent callers all see it).

The candidate contract is in [CONTRACT.md](CONTRACT.md). Promoted from delegate's health ledger; consumers adopt separately.
