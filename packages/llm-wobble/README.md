# llm-wobble

**Stop caring that an LLM's JSON envelope arrives fenced, prose-wrapped, or with
fields dropped.** Ask a model for JSON and you get ```` ```json ```` fences, a
trailing prose sentence, a second fence after the object, or a required field
simply missing. `llm-wobble` is the one funnel that decodes it, recovers each
field against a declared per-field policy, logs every recovery, and hands back a
typed value that a hand-rolled parse cannot forge.

```python
from llm_wobble import parse_with_policy, unwrap, WobblePolicy, WobbleTolerance

policies = {
    "answer": WobblePolicy(WobbleTolerance.STRICT),                     # missing → ParseError
    "sources": WobblePolicy(WobbleTolerance.DEFAULT, default=[]),       # missing → [] + one log event
    "score": WobblePolicy(WobbleTolerance.DERIVE, derive=lambda d: 0),  # missing → derived + one log event
    "note": WobblePolicy(WobbleTolerance.OPTIONAL, default=None),       # missing → None, silently
}

wobbled = parse_with_policy(
    raw_model_output,               # fenced / prose-wrapped / partial — all handled
    policies=policies,
    into=lambda d: MyPayload(**d),  # your typed constructor
    boundary="my_call",            # names the site in log events
    model="claude-...",
)
payload = unwrap(wobbled)           # MyPayload
```

## The contract

- **`json.loads` lives here and nowhere else.** With decode funnelled through one
  module, a consumer can ban `json.loads` across the rest of its LLM code (a
  simple AST test) and know no path skips the policy.
- **`Wobbled` is opaque.** Its only constructor is the funnel. Downstream code
  typed as `Wobbled` cannot accept a dict fabricated outside it — the bypass
  becomes a deliberate `type: ignore`, not an accident.
- **Recovery is per-field and declared, not ad hoc.** `STRICT` raises `ParseError`
  on a miss; `DERIVE` computes from the rest of the payload; `DEFAULT` substitutes
  a constant; `SKIP` raises `WobbleSkip` so the caller can short-circuit. Each of
  those fires exactly one `llm_wobble` log event.
- **`OPTIONAL` is the field the contract said could be absent.** It substitutes
  like `DEFAULT` but emits nothing and is not listed in `recovered_fields` —
  because nothing was repaired. Only the caller knows which fields its prompt
  marked optional, so the vocabulary carries it rather than the funnel guessing.
  Declaring an optional field `DEFAULT` is not a harmless over-report: a log key
  that fires on every healthy call cannot detect anything, and that is how the
  distinction was found.
- **Arrays too.** `parse_list_with_policy` expects a JSON array and filters entries
  through `item(dict) -> T | None`; malformed entries are dropped inside the funnel
  (one event names the dropped indices), never in caller code.
- **Recovery is visible.** `recovered_fields(wobbled)` names every field that fell
  back, so a caller can downgrade confidence or surface a hint.

## Logging is injected

Recoveries emit on the `llm_wobble` logger by default. Pass `logger=` to route
them onto a host's own managed channel:

```python
parse_with_policy(..., logger=my_app_logger)
```

A host that routes *everything* through one logger binds once instead of
repeating the kwarg:

```python
funnel = llm_wobble.bind(my_app_logger)
funnel.parse_with_policy(raw, policies=..., into=..., boundary=..., model=...)
```

Use `bind` rather than hand-rolling wrappers. A hand-written wrapper restates
the signature it wraps, so a parameter added here silently stops reaching your
call sites — `bind` is `functools.partial` underneath and has no second
signature to fall behind. An explicit `logger=` at the call site still wins.

The record is `message="llm_wobble"` with a `fields` payload on `record.fields`
(`boundary`, `field`, `tolerance`, `model`, `raw` — the raw excerpt is bounded to
200 chars). The package never names a consumer's logger.

## What stays with the consumer

The **policy tables** — which fields a given envelope requires and how each
recovers — are product, not mechanism. They live with the consumer that owns the
envelope shape. `llm-wobble` owns only how a policy is *applied*.
