# Changelog

## Unreleased

- `plan --explain` prints `affected: N changed file(s): <first 5> (+M more)`, not every path.

- `packages [--all]`: the package directories a change reaches (the changed ones, their dependents, the lock read per package), for a step that runs once per package.

- `[tool.any-gate.python.repo-reads]`: each repo test file keyed by the paths it reads; a change runs only the tests whose reads it touched (unkeyed tests always run). `reads_audit.audit_repo_tests` keeps the keys true.
- `[tool.any-gate.python.reads]`: a root file -> the packages whose tests read it. A change selects those packages and their dependents (not every package); `fingerprint`/`plan` hash the mapped files into their readers' keys; an unmapped path still selects every package. `reads_audit.audit` is the fitness check that keeps the map true; `reach(rules=)` measures a rule set.

## 0.3.0

- Reads child output through `Captured` (stream-proc 0.13.0): git and uv text via `.text`, the `git archive` tarball as bytes; requires `stream-proc>=0.13.0,<1`. Contract unchanged.

## 0.2.0

- Breaking: `run_tests(..., env=)` is required (the environment the pytest processes get and `nice` is found on); the CLI passes `os.environ`. `nice` is found with `child_env.find`. Git and `uv export` run through `stream_proc.capture` with a timeout; the per-package export hash is `content_digest.digest_text(length=64)`, the same bytes. Depends on `child-env`, `content-digest`, `stream-proc>=0.10`. No suite key changes.
- `plan` prints an alarm to stderr when the change reaches more than half of the package suites (`wide_alarm`, on `any_gate.too_wide`); it does not fail.
- `run --nice N` (default 10) and `run_tests(nice=)` start every pytest process that many steps nicer, so a gate yields the box to what the owner waits on.
- Dev group: the package's tests run isolated (`uv run --isolated --package any-gate-python --group dev pytest packages/any-gate-python/tests`).

## 0.1.2

- The `pytest` extra declares `pytest-xdist` (the runner passes `-n` to the pytest of the project under test).

## 0.1.0

- Extracted from the shelf's `tools/affected.py`: the workspace graph, the lock read per package, the selection, the per-suite fingerprint and `--reach`.
- The repo's own path rules moved to `[tool.any-gate.python]` in the root `pyproject.toml`.
- The pytest runner: `python -m any_gate_python run [--workers --wall --idle --pytest-args] PATH...`, `any_gate_python.stages.run_tests(paths, *, cwd, workers, ...) -> Outcome(stages, tests)` (stages parallel, serial, quarantine; lanes by `any_gate_python.lanes_plugin`, not `-m`), moved from `any-gate`. The selection verbs are now `python -m any_gate_python plan [--plan --explain --reach N]`; the package depends on `any-gate` and `stream-proc`.

- 0.1.1: isolated per-package test runs; contract unchanged.
