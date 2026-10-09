# asgi-token-gate

**Stop hand-writing the ASGI middleware that checks a token header.** One gate, two ways to
know a token: a static secret, or a live set of leases you mint and revoke.

```python
import asgi_token_gate as tg

# A static per-instance secret, minted once to a 0600 file and reused across restarts.
token = tg.stable_token(derived_root / "agent.token")
app = tg.StaticTokenGate(inner, token, header="X-App-Token")

# A live set: mint per job, revoke at exit; the next call after a revoke is refused.
leases: tg.LeaseSet[str] = tg.LeaseSet()
lease = leases.mint("job:transcribe")      # an unguessable token
app = tg.LeaseTokenGate(inner, leases, header="X-App-Token")
leases.resolve(lease)                      # 'job:transcribe'
leases.revoke(lease)                       # idempotent; effective on the next request

# Any other way to know a token: a predicate.
app = tg.TokenGate(inner, header="X-App-Token", accepts=lambda t: t in allowed)
```

## Rules

- Every `http` request must carry the header; a missing or refused token gets `401` with a
  JSON body `{"error": <deny_message>}` and the wrapped app is never called.
- Non-HTTP scopes (`lifespan`, `websocket`) pass straight through, so the wrapped app's
  own lifecycle still runs.
- Tokens are compared with `secrets.compare_digest`, the static one and each lease alike: a
  dict lookup short-circuits on the first differing byte, and its timing leaks a prefix.
- A lease has **no TTL**: each request re-resolves against the live set, so a day-long job
  keeps one token and a revoke takes effect at the next call. Leases live in memory only.
- `stable_token(path)` reads the token at `path`, or mints `secrets.token_urlsafe(32)` into
  a file created `0600` (parent folders included) and returns it.
- A header that is not valid UTF-8 is a refused token, not a crash.

Plain ASGI, no framework. Stdlib only.
