# Tasks: gate test loop

Each task is a bead with acceptance criteria (`bd lint` runs in the gate). Tests first. Done = `just check` green over the whole repo.

- [x] 1. Fitness test `tests/test_workspace_imports_are_declared.py`; `mcp-bridge` and `mcp-call` declare `async-scope[asgi]` in a dev group (2026-11-19).
- [ ] 2. Reproduce the unexplained unselected failure of `blueprint` `test_a_tree_checked_dirty_then_committed_whole_is_the_tree_that_passed` under the
      `atomic-io` mutation (it uses a temp repo; 0 failures in 25 solo, 6 parallel and 3 pair runs); read the 8 repo-root path hits in `packages/blueprint/tests`.
- [x] 3a. `process-lock::test_a_failure_while_locking_closes_the_descriptor` fixed at its root (2026-11-19): two `any-lease` tests left leases held in the
      process-wide lock registry, so `assert not held()` failed whenever an xdist worker ran them first (60 of 60 failures when the suites share a process).
      Released both leases; `packages/any-lease/tests/conftest.py` now fails any test that leaks a lease. 28 parallel mixed runs and 6 full parallel runs: 0 failures.
- [ ] 3b. `any-lease::test_sigterm_reaches_the_command_and_the_exit_code_says_so` failed once in 3 full parallel runs and not in 300 stress runs (28 at once),
      nor in 6 later full runs. Cause unknown; do not patch on a guess: when it recurs, keep the failing output (`-rf`, `--durations`), and put it in `quarantine` meanwhile.
- [x] 4. Per-package fingerprint = files + `uv export` hash; "lock changed" no longer selects all (2026-11-19). The root pyproject is read as: dependency tables via
      the exports, pytest and coverage settings as a change to every suite, everything else (ruff, pyrefly, import-linter, `tool.uv`, test paths) as no suite's
      concern; select-all stays for unknown paths, `.python-version` and when uv or the base tree cannot answer. `tools/affected.py --reach N` replays the last N
      commits: 50 commits give median 1, max 5 of 79 packages (before: median 79). A history replay is not a test (50 s, tied to this repo's past).
- [ ] 5. Second hub mutation (any hub other than `atomic-io`); record selected vs failing suites in the change's research folder.
- [x] 6. Receipts wired (2026-11-19): `tools/affected.py --plan` prints `path<TAB>key`; `any-gate test` skips suites whose key passed and records the rest when green; the ledger is
      `<git common dir>/gate-receipts.json`, shared by every worktree. `affected.py`'s own `.cache/affected-passed.json` is gone. `gate_state.py`'s whole-tree record and pre-push skip remain
      (consumers still copy it) and retire when the consumers move onto the gate packages.
- [x] 7. Run guard wired for `test-affected` (2026-11-19): auto workers (one process for 150 tests or fewer, cap 4), `serial` and `quarantine` markers declared in the root pyproject, stages by a lane plugin
      that leaves the repo's `-m "not browser"` in force (found by a failing test: a second `-m` would have run browser tests), wall 3600 s and idle 600 s through `stream-proc`. The box lock is
      an `any-lease` lease (`gate-leases`, 1 slot) for `test-affected` and `check-all`. Not done: `nice`, the too-wide alarm in the command, `quarantine` triage (no test uses it yet).
- [ ] 8. Declare each package's test dependencies in its own `pyproject.toml`; isolated per-package test run; investigate why `atomic-io` still
      fails collection in isolation; heavy-extra lanes.
- [ ] 9. Measure the box-wide lock on a loaded box (several concurrent gates) with and without receipts; decide lock vs slots; record.
- [ ] 10. Hooks per design D6; blueprint checkpoint wording lives in `blueprint-multi-stack-contracts`.
- [ ] 11. Post-merge or tag-time gate decision and the ADR amending 0021 and noting 0027.
- [ ] 12. `just check` green over the whole repo; `just check-all` once locally; archive.
