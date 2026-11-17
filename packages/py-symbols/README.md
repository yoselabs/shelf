# py-symbols

Stop walking `ast` by hand to name Python code. Find a symbol's source by dotted name, list a module's functions
qualified, ask which function encloses a line, and hash one symbol's source so a change to anything else leaves it
alone. Stdlib only.

```python
from py_symbols import find, functions, innermost, symbol_hash

span = find(source, "Loan.renew")   # Span(name, start, end, text, body) or None
spans = functions(source)           # qualified, outer before inner: "Loan.renew", "Loan.renew.inner"
innermost(spans, 16)                # "Loan.renew.inner": the deepest function whose body holds line 16
symbol_hash(source, "late_fee")     # 12 hex of sha256 over the symbol's text, None when absent
```

| call | job |
|---|---|
| `find(source, symbol)` | module-level def, class, assignment, annotated assignment or `type` alias; `Class.member` at any depth through classes; None when absent or unparsable |
| `functions(source)` | every function and method (classes only qualify), outer first; [] when unparsable |
| `innermost(spans, line)` | name of the deepest span whose body holds `line`, None outside every function |
| `symbol_hash(source, symbol, *, length=12)` | sha256 hex prefix of `find(...).text` |

`Span.start`/`end` are 1-based inclusive lines and include decorators; `body` is the first body line (a decorator or
`def` line runs when its enclosing scope does, not when the function is called). `text` is the source of exactly those
lines, so a decorator change changes the hash and a change elsewhere in the file does not.
