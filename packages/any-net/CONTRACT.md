# Online probe with a DNS/TCP split and drop detection

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

- `probe(hosts=None, budget_s=2.5, *, connect_s=1.5, resolve=, connect=, clock=) -> Probe`: one thread per host plus the
  IP literal `1.1.1.1:443`; the join deadline `budget_s` bounds the whole call; a host still running then is `slow`.
  Per host: `ok` | `dns` (resolve failed) | `tcp` (connect failed) | `slow`. IPv4 literals skip resolving. No host given
  tests `one.one.one.one:443`.
- `Probe.up`: some named host is `ok`. `ip_up`: the literal is `ok`. `why`: `ok`, else `dns` (a name failed to resolve and the
  literal answers), else `vendor` (the literal answers), else `offline`.
- `looks_dropped(text) -> bool`: case-insensitive match on connection-failure phrases; `stream disconnected` followed within
  200 characters by `max_output_tokens` is not a drop. `None` and empty are False.
- `record(path, probe) -> Probe`: creates the parent directory, atomic replace; `since` is kept while `up` is unchanged.
  Swallows `OSError`/`ValueError` (nothing stored, no signal) and removes its temp file on failure.
- `last(path) -> Probe | None`: the stored probe whatever its age; None when absent, unreadable or malformed.
- `cached(path, fresh_s=120) -> Probe | None`: `last`, or None when older than `fresh_s`.
- `view(probe, hosts, now, fresh_s=120) -> View(up, since, age_s)`: `up` is None for no probe or a stale one (`since`, `age_s`
  kept); otherwise True when any tested host of `hosts` is `ok`; hosts the probe never tested say nothing, and with none tested
  `up` is the probe's own.

Drift from delegate's `netprobe.py`: `probe()` returns a frozen `Probe` (attributes, not a dict; `per_host` for `hosts`);
`connect_s`, `resolve`, `connect`, `clock` are keyword-only; `record` has no `clock` parameter (it stores `probe.at`);
`load` is `last`; `view` takes a `Probe`, not a dict, and returns a `View`.

No consumer app is imported. Executable acceptance: `tests/`.
