# Tasks: gate test loop

Each task is a bead with acceptance criteria (`bd lint` runs in the gate). Tests first. Done = `just check` green over the whole repo.

- [x] 1. Fitness test `tests/test_workspace_imports_are_declared.py`; `mcp-bridge` and `mcp-call` declare `async-scope[asgi]` in a dev group (2026-11-19).
- [x] 2. (2026-11-20, `research/2026-11-20-flakes-mutation-lock.md`) Reproduce the unexplained unselected failure of `blueprint` `test_a_tree_checked_dirty_then_committed_whole_is_the_tree_that_passed` under the
      `atomic-io` mutation (it uses a temp repo; 0 failures in 25 solo, 6 parallel and 3 pair runs); read the 8 repo-root path hits in `packages/blueprint/tests`.
      Done: the old test ran a recipe that never imported `atomic-io` (coincidence, not a selection hole) and read no live checkout; its moved copy in `any-gate` reproduced 1 in 40 loaded runs;
      root cause a racily-clean index copy in `GateState` (`copyfile` stamped the copy now); fixed with `copy2`, pinned by a deterministic test; 0 in 120 after.
- [x] 3a. `process-lock::test_a_failure_while_locking_closes_the_descriptor` fixed at its root (2026-11-19): two `any-lease` tests left leases held in the
      process-wide lock registry, so `assert not held()` failed whenever an xdist worker ran them first (60 of 60 failures when the suites share a process).
      Released both leases; `packages/any-lease/tests/conftest.py` now fails any test that leaks a lease. 28 parallel mixed runs and 6 full parallel runs: 0 failures.
- [x] 3b. (2026-11-20) `any-lease::test_sigterm_reaches_the_command_and_the_exit_code_says_so` failed once in 3 full parallel runs and not in 300 stress runs (28 at once),
      nor in 6 later full runs. Root cause: the test's child slept once for 60 s after installing its handler, and CPython's `time.sleep` misses a signal that lands before its first syscall (3 hangs in 7600 loaded runs; the handler ran at 60 s with rc 7). Fixed in the test (50 ms slices); 0 in 8000 after. No `any-lease` defect; no other suite has the pattern.
- [x] 4. Per-package fingerprint = files + `uv export` hash; "lock changed" no longer selects all (2026-11-19). The root pyproject is read as: dependency tables via
      the exports, pytest and coverage settings as a change to every suite, everything else (ruff, pyrefly, import-linter, `tool.uv`, test paths) as no suite's
      concern; select-all stays for unknown paths, `.python-version` and when uv or the base tree cannot answer. `tools/affected.py --reach N` replays the last N
      commits: 50 commits give median 1, max 5 of 79 packages (before: median 79). A history replay is not a test (50 s, tied to this repo's past).
- [x] 5. (2026-11-20) Second hub mutation, `stream-proc`: 6 package suites selected, 23 failures, all inside them; none outside (`research/2026-11-20-flakes-mutation-lock.md`).
- [x] 6. Receipts wired (2026-11-19): `tools/affected.py --plan` prints `path<TAB>key`; `any-gate test` skips suites whose key passed and records the rest when green; the ledger is
      `<git common dir>/gate-receipts.json`, shared by every worktree. `affected.py`'s own `.cache/affected-passed.json` is gone. `gate_state.py`'s whole-tree record and pre-push skip remain
      (consumers still copy it) and retire when the consumers move onto the gate packages.
- [x] 7. Run guard wired for `test-affected` (2026-11-19): auto workers (one process for 150 tests or fewer, cap 4), `serial` and `quarantine` markers declared in the root pyproject, stages by a lane plugin
      that leaves the repo's `-m "not browser"` in force (found by a failing test: a second `-m` would have run browser tests), wall 3600 s and idle 600 s through `stream-proc`. The box lock is
      an `any-lease` lease (`gate-leases`, 1 slot) for `test-affected` and `check-all`. Leftovers done 2026-11-20: `any_gate_python run --nice` (default 10), the `plan` too-wide alarm on stderr, quarantine triage (nothing to quarantine: both known flakes fixed at the root).
- [x] 8. (2026-11-20) Declare each package's test dependencies in its own `pyproject.toml`; isolated per-package test run; investigate why `atomic-io` still
      fails collection in isolation; heavy-extra lanes.
      Done: every package with tests has a `dev` group (pytest, pytest-asyncio, hypothesis, what its tests import); `tests/test_package_tests_declare_their_dependencies.py`; `atomic-io` failed alone on an undeclared `pytest_bdd`; all 83 packages pass `uv run --isolated --package X --group dev pytest packages/X/tests`. The shared root dev group stays until task 12.
- [x] 9. (2026-11-20) Measure the box-wide lock on a loaded box (several concurrent gates) with and without receipts; decide lock vs slots; record.
      Done: receipts were read before queueing, so a queued gate reran what the holder passed; now re-read once the slot is held (4 same-closure gates 130 s -> 30 s). Decision: one slot stays the default; `--slots` exists; slots only win for different closures on an idle box, and that measurement was too noisy to trust.
- [x] 10. Hooks per design D6 (2026-11-19): the commit hook already ran only bd hooks and linters on staged files (no tests); pre-push runs the gate through `gate_state.py`'s whole-tree
      skip (kept for now: fitness tests carry no receipt, so the tree skip still saves the most; it moves into `any-gate` with the consumers' migration). Blueprint checkpoint wording lives in `blueprint-multi-stack-contracts`.
- [x] 11. Post-merge gate (2026-11-19): `gate-after-merge` hook runs `just check` on a merged tree (skipped when that tree passed); ADR 0027 records it. Tested: `prek run --hook-stage post-merge` passes.
- [ ] 12. `just check` green over the whole repo; `just check-all` once locally; archive.
