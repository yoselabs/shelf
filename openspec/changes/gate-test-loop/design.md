# Design: gate test loop

## Measured basis (all 2026-11-19, shelf fad2bb8, Linux aarch64, 14 cores, idle)

| fact | value |
|---|---|
| clean-diff `just check` / leaf / hub change | 16 s / 15 s / 13 s |
| `just check-all` | 93 s (tests 92 s) |
| last 50 commits touching `uv.lock` | 45 |
| package suites selected, today's rule / lock read per package | median 79 / 1.5 (max 5, none select all) |
| `uv export --package X` for 79 packages | 1.7 s, deterministic across runs |
| isolated per-package venv run vs shared venv (`any-yaml`) | 0.9 s vs 1.2-1.6 s |
| task-loop file-level closure vs shelf package selector, 20 commits | 63.5 (as is) / 33.5 (strings rule off) vs 34.5 test files; strings rule is the difference |
| mutation of hub `atomic-io` | 4 dependants caught; 1 blueprint test failed unselected once and was not reproduced (25 solo runs, 6 parallel runs, the original pair); 1 flaky |
| 3 full parallel runs (79 suites plus `tests/`, 14 cores) | 2 green, 1 red from `any-lease` sigterm test: flakiness is a property of the loaded suite |

## Decisions proposed

### D1. Fingerprint of a package = its files + the `uv export` hash of its runtime and dev set (+ dependants through the graph)

`uv export --frozen --package X --group dev --no-emit-workspace --no-hashes` is uv's own answer to "what does X install", so
nothing custom tracks the lock format. Hash it per package, compare with the last green run. Rejected: parsing `uv.lock` ourselves
(tracks a format uv owns), splitting the lock (uv allows one lock per workspace; several workspaces break editable links), keeping
"lock changed, select everything" (the measured defect). Unknown paths and `requires-python`, `.python-version`, uv and Python versions
still select everything: they are outside the export.

A shared dev set (63 of 79 packages export the identical 169 lines) means a dev-dependency bump reruns about 63 suites. That is correct
for a shared environment; per-package test dependencies (D5) shrink it.

### D2. Selection granularity stays at package level

File-level closure was within 0-2 files of the package selector once task-loop's basename "strings" rule is excluded; shelf commits
change one package's src, tests, README and pyproject together. Extra precision is deferred until a package-level selection is
measured too wide (`reach` report alarm). `test-reach` (per-test function reach) remains the candidate for finer selection later.

### D3. Receipts

Key = hash of: tool version, python and uv versions, the selected test ids, the fingerprints of their packages, the root inputs every run
reads (`conftest.py`, root `pyproject.toml` minus the lock rule), and the gate step name. Stored in a repo-local, git-ignored directory,
shared by hooks and manual runs. A receipt is written only on exit 0 (or 5, no tests collected). `tests/` (fitness) is never skipped.
Rebase and amend keep the key when the closure is unchanged: this replaces the byte-identical-tree skip in `gate_state.py`. Task-loop's
"carry" idea (re-store under a new key when only the base moved) is covered by the key not including the base.

### D4. Run guard (extracted from task-loop `dev/runtests.py`, written for pytest only)

workers = min(free cpus, RAM / 2 GB, ceil(tests / 150), cap); at most the small-selection threshold runs without xdist; wall limit 3600 s
and idle limit 600 s kill the process tree; `serial` tests run after the parallel group; `quarantine` tests run apart and cannot fail the
run; a selection over half of all tests prints an alarm (it does not fail). The box-wide test lock (flock) is kept at first; the
open question is whether core-aware slots beat one lock once receipts make queued gates skip. Measure on a loaded box before changing it.

### D5. Environments

Each package's `pyproject.toml` declares the test dependencies its suite needs (root `conftest.py` imports `hypothesis` and no package
declares it; an isolated run failed on it). With that done, tests may run isolated per package. Isolation did not cost startup time
(0.9 s warm), so the choice rests on benefit: a heavy-extra bump reruns only its users. Heavy extras become opt-in lanes (precedent
`test-browser`). Proposed default: isolated per-package runs for packages that declare their own dev group; the shared group is
removed once every package declares its own (hard opinion, ADR 0028: no two ways).

### D6. Hooks

| hook | runs |
|---|---|
| pre-commit | bd hooks; linters on staged files (ruff, shellcheck, codespell; secret scan on the staged diff, see `blueprint-multi-stack-contracts`); never tests |
| pre-push | the gate under receipts; bd dolt push |
| post-merge | the gate on the merged tree, or a tag-time `just check`, decided in tasks |
| tag | full run with the coverage floor |

### D7. Pytest only

No `coverage run` wrapper, no non-pytest runner in the gate. Coverage via pytest's plugin on the full run. (a2kay's coverage.py
wrapper existed because pytest-cov breaks duckdb's lazy C-extension import; that consumer decision moves with its migration, see
`gate-kit-package`.)

## Rejected

- moon, Turborepo, Nx, Pants as the orchestrator now: ADR 0021's trials still hold and no non-Python package exists yet. The
  re-open trigger is handled in `gate-kit-package`.
- Adopting task-loop's file-level selector or its strings rule: no precision gain here, 30 extra files per commit.
- Receipts keyed on the tree only: break on amend and rebase.

## Risks and unknowns

- Replay of the export rule counts selection; it does not prove no test is skipped. One hub mutation found an unexplained, unreproduced
  unselected failure. A second hub mutation, repeated to catch it, and a loaded-box lock measurement are tasks.
- Flaky tests: `process-lock` and `any-lease` (signal and descriptor timing under load); the `quarantine` lane plus a fix per flake.
- Hook design assumes prek stays the hook manager (ADR 0020).
