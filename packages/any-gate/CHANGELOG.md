# any-gate — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.1.0: `GateState(repo, receipts)` with `start()`, `passed(gate) -> bool`, `green(gate) -> bool` (key `<tree> <base>`, receipt `gate-<gate>`); verbs `python -m any_gate start|passed|pre-push [--repo --receipts --gate] [-- CMD]` (default receipts: `gate-receipts.json` in the git common dir); `python -m any_gate test --receipts FILE [--lease-root --slots --workers --wall --idle --cwd] [-- PYTEST_ARGS]` reads plan lines `path<TAB>key`; `run_tests(paths, *, cwd, workers=1|None, ...) -> Outcome(stages, tests)` (stages parallel, serial, quarantine; lanes by `any_gate.lanes_plugin`, not `-m`); `workers(tests, Resources, ...)`, `Resources`, `detect()`, `too_wide()`; `key(**parts) -> str` (32 hex, canonical JSON, order-free, refuses non-JSON); `Receipts(path, *, keep=50)` with `has(name, key) -> bool`, `record(name, key)`; file `{"version": 1, "receipts": {name: [keys, newest first]}}`.
