# any-net

Stop re-writing "am I online?". `probe` resolves and connects to your hosts at once, tells a DNS outage from a refused
vendor from no network, and returns by a deadline even when the resolver hangs. `looks_dropped` says whether an error
text is a broken connection. `record`/`cached` keep the last probe in one file so a status read opens no socket. Stdlib only.

```python
from any_net import cached, looks_dropped, probe, record

p = probe(["api.vendor.com"], budget_s=2.5)
if not p.up:
    print(p.why)            # dns | vendor | offline
record("net.json", p)
assert looks_dropped("Error: getaddrinfo ENOTFOUND api.vendor.com")
fresh = cached("net.json", fresh_s=120)   # Probe, or None when absent or older than 120 s
```

| call | job |
|---|---|
| `probe(hosts=None, budget_s=2.5, *, connect_s=, resolve=, connect=, clock=)` | `Probe(up, ip_up, why, per_host, at, ms, since)`; `resolve`/`connect`/`clock` injectable |
| `looks_dropped(text)` | the text names a connection failure (ECONN*, DNS, TLS handshake, "stream disconnected"); not the model's output cap |
| `record(path, probe)` | atomic write; `since` moves only when `up` flips; never raises |
| `cached(path, fresh_s=120)` | the stored `Probe`, or None when absent, corrupt or stale |

Policy (which hosts matter, what to do on `dns` vs `offline`) stays with the host. Contract: [CONTRACT.md](CONTRACT.md).
