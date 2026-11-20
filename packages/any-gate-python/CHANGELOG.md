# Changelog

## 0.1.2

- The `pytest` extra declares `pytest-xdist` (the runner passes `-n` to the pytest of the project under test).

## Unreleased

- `plan` prints an alarm to stderr when the change reaches more than half of the package suites (`wide_alarm`, on `any_gate.too_wide`); it does not fail.
- `run --nice N` (default 10) and `run_tests(nice=)` start every pytest process that many steps nicer, so a gate yields the box to what the owner waits on.
- Dev group: the package's tests run isolated (`uv run --isolated --package any-gate-python --group dev pytest packages/any-gate-python/tests`).

## 0.1.0

- Extracted from the shelf's `tools/affected.py`: the workspace graph, the lock read per package, the selection, the per-suite fingerprint and `--reach`.
- The repo's own path rules moved to `[tool.any-gate.python]` in the root `pyproject.toml`.
- The pytest runner: `python -m any_gate_python run [--workers --wall --idle --pytest-args] PATH...`, `any_gate_python.stages.run_tests(paths, *, cwd, workers, ...) -> Outcome(stages, tests)` (stages parallel, serial, quarantine; lanes by `any_gate_python.lanes_plugin`, not `-m`), moved from `any-gate`. The selection verbs are now `python -m any_gate_python plan [--plan --explain --reach N]`; the package depends on `any-gate` and `stream-proc`.

- 0.1.1: isolated per-package test runs; contract unchanged.
