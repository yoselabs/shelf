# Python symbols

Status: **candidate**. Shape: flexible. Protection is not yet earned by a live consumer.

- `find(source, symbol) -> Span | None`: a module-level def, class, assignment, annotated assignment or `type` alias; a dotted name enters classes only. A name bound by a multi-target assignment is found by each target. None for a missing name or a `SyntaxError`.
- `Span(name, start, end, text, body)`: 1-based inclusive lines, decorators included in `start` and `text`; `body` is the first body line of a function or class, `start` otherwise.
- `functions(source) -> list[Span]`: every function, method and nested function, qualified by enclosing classes and functions, outer before inner (source order); classes qualify names but are not listed. [] for a `SyntaxError`.
- `innermost(spans, line) -> str | None`: the deepest span whose `body..end` holds `line`.
- `symbol_hash(source, symbol, *, length=12) -> str | None`: lowercase sha256 hex prefix of `find(...).text`; stable under edits outside the symbol.

No consumer app is imported. Executable acceptance: `tests/`.
