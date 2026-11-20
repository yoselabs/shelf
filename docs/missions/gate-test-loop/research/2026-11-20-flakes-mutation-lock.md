# Flakes, a second hub mutation, isolated runs and the box lock (2026-11-20)

Linux aarch64, 14 cores, a box shared with five other sessions (load average 2 to 23 while measuring; stated per row). Beads `shelf-wctp.1` to `.6`.

## Task 3b: `any-lease` sigterm test: root cause

Not an `any-lease` bug. The test's child installs a SIGTERM handler and then calls `time.sleep(60)`. CPython's sleep does not check for a pending
signal before its first `clock_nanosleep`: a SIGTERM that lands in that window (the test sends it the moment it reads `ready`) sets the flag but does
not interrupt the syscall, so the handler runs when the 60 s sleep ends. The wrapper had forwarded the signal (a debug copy logged `forward 15 child=True`).

Evidence: 7600 runs of the test body on 40 busy loops: 3 hangs (the wrapper alive, the child asleep, `SigCgt` showing the handler installed). On a hang the probe waited
on: `rc=7, out="got term"` at 60 s, empty stderr, so the signal had arrived and only the handler was late. Fix, in the test: the child sleeps in 50 ms slices
(as the wrapper itself does), so the handler always gets to run. After: 0 hangs in 8000 runs under the same load. Other suites: no other child
has a Python handler on one long sleep (the rest use the default or ignored disposition, or raise the signal themselves), so nothing else is exposed.

## Task 2: the unselected `blueprint` failure

The test (`test_a_tree_checked_dirty_then_committed_whole_is_the_tree_that_passed`) lived in `blueprint/tests/test_recipes.py` and ran the copied `gate_state.py`
recipe in a subprocess; that script never imported `atomic-io`, so a failure under the `atomic-io` mutation was a coincidence of load, not a selection hole. The recipe
and the test moved into `any-gate` (#120); `any-gate` depends on `atomic-io`, so the test is now selected by it. The `blueprint` tests read no live checkout: the 8 path hits are
`Path(__file__).parent` fixtures and a `cwd=` of the tests folder.

The flake itself reproduced on the moved test: 1 failure in 40 runs of `test_state.py` (8 workers, 20 busy loops). Root cause: `working_key` computes the tree from a *copy* of the
index (`shutil.copyfile`), and the copy's mtime is now. Git trusts an entry's recorded stat unless the entry is racily clean (not older than the index file), so a copy
stamped now makes every entry look safe: an edit of the same size made in the entry's own timestamp tick (a test writes `x = 1`, then `x = 2`) is not rehashed, the stale
blob lands in the recorded tree, and `green` says no after the commit. Fix: `shutil.copy2` keeps the index's mtime. A deterministic test
(`test_a_same_size_edit_in_the_same_timestamp_tick_still_counts_as_an_edit`) pins the mechanism with `core.trustctime=false`, `core.checkstat=minimal` and fixed mtimes; it failed before
the fix. After the fix: 0 failures in 120 runs of the file (the busy loops ran for the first 150 s of them). The defect was real in the shipped `any-gate pre-push` path too: the usual cost is a gate rerun, and in principle a later commit of the stale content could match the wrong record and skip a gate.

## Task 5: second hub mutation: `stream-proc`

Mutation: `stream_proc.runner.run` reports a clean exit as 1 (`code = 1 if p.returncode == 0 else p.returncode`). Selection by `affected()` for that one file: 6 package suites
(`any-agent`, `any-gate`, `any-gate-python`, `anyllm`, `llm-cache`, `stream-proc`) and the repo's own tests. The whole suite (every package, `-n 10`, 85 s) then failed 23 tests,
all in selected suites: `any-gate-python` 9, `stream-proc` 8, `any-gate` 4, `any-agent` 1, plus one repo-level fitness test that failed for an unrelated reason (a bug in the
fitness test written the same day, fixed). Failures outside the selection: none. Together with the `atomic-io` mutation (4 dependants caught; the one unselected failure explained above)
selection is exact for both hubs tried.

## Task 8: isolated runs

`uv run --isolated --package X --group dev python -m pytest packages/X/tests` needs the package to declare what its tests import. `atomic-io` failed collection alone because its tests import
`pytest_bdd`, which nothing in its `pyproject.toml` named (the shared dev group hid it); the root `conftest.py` also imports `hypothesis` and the root pytest settings name `pytest-asyncio`.
Every package with tests now has a `dev` group with `pytest`, `pytest-asyncio`, `hypothesis` and what its tests import
(`tests/test_package_tests_declare_their_dependencies.py` enforces both, extras not counted: `--group dev` does not install them). The first sweep of the 83 packages found 10 more
that failed alone for reasons an import scan cannot see (an extra a test needs, a tool a test runs as a subprocess: `ruff`, `pyrefly`, `pytest-xdist`, `fastmcp-slim[server]`, `pyyaml`); declared, and
all 83 pass isolated (91 s wall for the sweep at 5 at once, cold; 0.6 to 16 s each). The sweep is the proof; the fitness test only guards imports.

The shared dev group stays for now: removing it is task 12's decision (ADR 0028, one way), because the root `uv sync` and the linters still need it. `convert-md`, `anyllm`, `any-browser`, `a2effect` and
`async-scope` name their own extras in their `dev` group (`self[extra]`); heavy-extra lanes (`anyembed`'s torch and llama, the browser engines) stay out of the `dev` group: their tests skip when the engine is
missing, and `just test-browser` is the lane that installs a browser.

## Task 9: the box lock

Eight suites (about 30 s alone), 4 gates started at once, 14 cores, load 9 falling to 2 during the first batch:

| gates | slots | receipts | wall |
|---|---|---|---|
| 1 | 1 | none | 30 s |
| 4 | 1 | none (each its own) | 130 s |
| 4 | 1 | shared, before the fix | would be 130 s: the receipts were read before queueing |
| 4 | 1 | shared, after the fix | 30 s (3 of 4 gates skipped everything) |
| 4 | 2 | none | 61 s |
| 4 | 4 | none | 32 s |

Finding: receipts were read before a gate queued, so a queued gate reran suites the holder had just passed. `any-gate test` now asks again once it holds the slot (`test_a_gate_that_waited_for_the_slot_skips_what_the_holder_passed_meanwhile`): the same-closure case collapses to one run.

Decision: keep one slot (the lock) as the default. The wait is real only for gates with different closures, and there more slots win only while the box has idle cores (4 slots ran 4 identical gates in the
time of one, because one gate's pytest uses a few cores); but `serial` tests assume the box is theirs, and a second measurement with overlapping plans under other sessions' load (load 1.4 to 23) was
too noisy to read and had one red gate at 3 slots that I could not explain. `any-gate test --slots N` exists for a box that wants it. Revisit with a measurement under a controlled load
if the queue notice ("waiting for a test slot") shows waits over a minute in real use.

## Task 7 leftovers

- The too-wide alarm: `any_gate_python plan` prints to stderr when a change reaches more than half of the package suites (`any_gate.too_wide`, `wide_alarm`); it does not fail.
- `nice`: `any_gate_python run --nice N` (default 10) starts every pytest process N steps nicer than the caller; the justfile's `test-affected` line needs no change.
- Quarantine triage: no test is quarantined and none needs to be. The two known flakes are fixed at the root (`process-lock` leaked leases in 3a; this file's 3b). Nothing in `packages/*/tests` carries `xfail` or a retry.
