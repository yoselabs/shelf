# any-contract

**The neutral half of a wire contract between two programs.** A caller and the tool it drives each keep a codec for
the same JSON (msgspec on one side, dataclasses on the other); the codec stays theirs. What both need the same
way is here. Standard library only.

```python
from any_contract import check_contract, diff_schema, undeclared

bad = check_contract(4, reply, capabilities=["writer_exec_allow"])   # reply: parsed object or JSON text
if bad:                                                              # a Violation, never an exception
    result = synthesize_stop("contract_violation", bad.text)         # yours

found = diff_schema(local_mirror_schema, published_schema)           # {".a.fields": (only_local, only_remote), ...}
new, resolved = undeclared(found, KNOWN_DRIFT)                       # fail the test on either list
```

## Rules

- **`check_contract(local_number, remote, *, key="contract", capabilities=(), capabilities_key="capabilities")`** returns
  `None` or a `Violation(text)`: not JSON, not an object, another number, or a capability the remote does not list (a list
  or a single string). The text carries at most 300 characters of what the remote sent.
- **`diff_schema(want, have)`** compares two JSON schemas by field names (`properties` plus `required`) and `enum`
  values, recursing into properties, `items` (`[]`), `additionalProperties` (`{}`) and `anyOf`/`oneOf` (`[i]`).
  Keys are `<path>.fields` and `<path>.enum`; a value is `(only in want, only in have)`, sorted.
- **`undeclared(found, known)`** takes `known = {path: (only_want, only_have, reason)}`: the drift you accepted, exactly.
  It returns `(new, resolved)`, so a fixed drift cannot stay listed and a grown one is reported.
- Out of scope: the codec, schema generation, and token-lean wire formats (`lean-wire`, `mcp-result-wire`).
