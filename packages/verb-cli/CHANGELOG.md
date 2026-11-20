# verb-cli — changelog

AI-facing only: one line per contract-shape change (old ⇒ new).

- 0.3.0: breaking  ⇒  `flags_of(fn, *, choices=False)` loses `choices`; new `choice_flags_of(fn)` (the old `choices=True`: a `Literal` or `Enum` of one value type is argparse choices); `flags_of(fn)` is the old default (one JSON flag); `VerbCli` uses `choice_flags_of`, as before
