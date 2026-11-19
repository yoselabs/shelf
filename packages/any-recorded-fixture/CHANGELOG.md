# any-recorded-fixture — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new. `Case(group, case, dir, meta)`; `cases(root)`; `read_json(path)`; `write_json(path, obj)`; `record(root, group, case, files, meta, *, text=None)`; `golden(path, actual, *, update)`; `GoldenMismatchError`; `update_requested(env=os.environ, name="UPDATE_GOLDEN")`; `scrub(text, **placeholders)`
- 0.2.0: `update_requested(env=os.environ, name="UPDATE_GOLDEN")`  ⇒  `update_requested(env, name="UPDATE_GOLDEN")` (`env` required, the process environment is never read)
