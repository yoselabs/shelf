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
- `record(path, probe) -> Probe`: atomic replace; `since` is kept while `up` is unchanged. Swallows `OSError`.
- `cached(path, fresh_s=120) -> Probe | None`: None when absent, unreadable, malformed or older than `fresh_s`.

No consumer app is imported. Executable acceptance: `tests/`.
