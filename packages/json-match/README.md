# json-match

**Stop rewriting how a test step reads and compares a JSON value.** A step quotes a path and
some text; this package turns that into a read and a verdict.

```python
from json_match import MISSING, compare, dig, matches

dig(result, "items.0.ref")            # a number indexes a list, -1 the last
dig(result, "items.*.ref")            # * maps over a list
dig(result, "nope") is MISSING        # absent, apart from a key holding null
compare(result["tags"], "contains", "ops")       # some item contains the text
compare(result["ids"], "is", "c/31, c/32")      # a list compares joined by ", ", in order
matches({"meta": {"kind": "project"}}, result)  # only the keys named are checked
```

## Rules

- **Text comparison.** A string compares as is, anything else by its JSON text (`true`,
  `22`); a list as its items' text joined by `", "`. `is more than` compares numbers.
  `OPS` lists every operator, longest first, ready for a step regex.
- **Subset match.** Every key named must be present with that value; objects match
  recursively; a list of objects matches when each expected object matches some actual
  item; a list of plain values must hold the same values in any order.
- **Missing is not null.** `dig` returns `MISSING` for a key, index or path that is not
  there, so a step can tell "absent" from "present and null".
- No dependencies. Tests are Gherkin (`tests/features/`).
