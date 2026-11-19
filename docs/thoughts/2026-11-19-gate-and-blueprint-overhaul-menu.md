# Gate, test loop and blueprint overhaul: the menu (2026-11-19)

Raw thinking, unresolved. Orientation and measurement done on a Linux DevBox (14 cores, idle) on 2026-11-19; the
owner's direction is "do it right, no backward compatibility, no shortcuts; if task-loop's design is better, extract it
into a package and adopt it". Nothing here is decided. Each row is a candidate item for a mission (`docs/missions/`); the
measured facts come first because the design rests on them.

## 1. Measured facts (shelf worktree on main, fad2bb8)

| fact | number | how |
|---|---|---|
| `just check` on a clean diff | 16 s wall | ran |
| `just check`, leaf change (`argparse-mcp`) / hub change (`atomic-io`, 4 dependants) | 15 s / 13 s | ran, temporary edit reverted |
| `just check-all` (all 79 suites) | 93 s wall, tests 92 s | ran |
| Same clean-diff gate on the owner's loaded Mac | 818 s, of which 789 s waiting for the box-wide test lock | owner's session, earlier |
| Commits of the last 50 whose diff touches `uv.lock` | 45 (5 more touch root `pyproject.toml`) | git |
| Same 50 commits, package suites selected by today's `tools/affected.py` | median 79 (all), 45 of 50 select all | replayed |
| Same 50 commits, selection by per-package `uv export` hash instead of "lock changed" | median 1.5, max 5, 0 select all | replayed |
| `uv export --package X` for all 79 packages | 1.7 s total, byte-identical across two runs | ran |
| Isolated per-package venv run (`uv run --isolated --package any-yaml --with ...`) | 0.9 s warm vs 1.2-1.6 s in the shared venv | ran |
| Mutation of a hub (`atomic-io` write drops a byte): failing suites | 4 selected and failed; 1 `blueprint` test failed unselected once and did NOT reproduce later (25 solo runs, 6 parallel, the original pair); `process-lock` failed once in parallel and passes alone | ran |
| 3 full parallel runs on the clean tree | 2 green, 1 red: `any-lease` sigterm test | ran |
| Undeclared workspace imports (tests of `mcp-bridge`, `mcp-call` import `async-scope`) | 2 edges | AST scan |
| `main` was red on a clean diff: `use-cases/README.md` and `ledger/README.md` stale vs their TOML | 2 lines | ran; regenerated locally, uncommitted |

Reading: the slowness is not test volume. It is (a) the select-everything rule on `uv.lock`, (b) queueing behind a
box-wide lock when many agent sessions gate at once, (c) the same tests run up to three times per change.

## 2. The menu

### A. Test strategy (pytest only)

| item | what | evidence |
|---|---|---|
| A1 | Select by changed package plus dependants, with the lock read per package (`uv export` hash of each package's runtime and dev set), not "lock changed, select all" | 45/50 commits select all today |
| A2 | Fitness test: every workspace-internal import is a declared dependency (closes the 2 undeclared edges; `deptry` does not see workspace edges) | AST scan |
| A3 | Flaky tests (`process-lock`, `any-lease` seen so far) get a `quarantine` lane and a fix each; check whether any package test really reads the live checkout (8 path hits in blueprint's tests, not read yet) | parallel runs |
| A4 | Markers: `serial` (runs alone), `quarantine` (flaky, cannot block, listed in a file), `slow`/`real`/`e2e` out of the gate, one place that defines them | task-loop, a2kay |
| A5 | Runner policy: worker cap from cores, RAM and test count; single process for small selections; hang guards (wall and idle); "selection too wide" alarm; `nice` for non-landing runs | task-loop `dev/runtests.py` |
| A6 | Receipts: a green result stored under a key of its closure (selected tests, their inputs, toolchain), reused across amend, rebase, hooks and the agent's manual run | task-loop gate-host design; shelf's cache is local fingerprints only |
| A7 | Full run with coverage only on tag (and on schedule); drop `coverage run` wrappers; coverage checkpoint tool-agnostic (shelf-2hl) | a2kay override |
| A8 | Selection reach report: a command that prints how many suites each recent commit selects (task-loop `dev/reach.py`); an alarm when the median creeps up | `reach.py`; measured by hand here |
| A9 | Possible finer selector from `test-reach` (per-test function reach) and `py-symbols`; only if the package level proves too coarse after A1 | untested |
| A10 | Flaky triage: `process-lock::test_a_failure_while_locking_closes_the_descriptor` | one parallel failure |

### B. Workspaces and environments

| item | what | verdict so far |
|---|---|---|
| B1 | Split `uv.lock` into several | ❌ `uv` keeps one lock per workspace; several workspaces break editable links and the single sync |
| B2 | Keep one workspace; declare each package's own test dependencies in its own `pyproject.toml` | needed for isolation: root `conftest.py` imports `hypothesis` and no package declares it |
| B3 | Per-package isolated venvs for tests (`uv run --isolated --package X`) | startup is not slower (0.9 s warm); the gain is that a heavy-extra bump reruns only its users, and a package proves its own dependencies. `atomic-io` still errors at collection in isolation; unexplained |
| B4 | Heavy extras (torch, transformers, llama, browser) become opt-in lanes (`test-browser` is the precedent) | 5.3 GB shared venv |

### C. Hooks and the gate (stop running tests many times)

| item | what |
|---|---|
| C1 | Commit hook: staged-file linters and the bd hooks only; never tests |
| C2 | Pre-push: the gate once, skipped when a receipt exists for the closure (not only for a byte-identical tree) |
| C3 | An ungated merge (GitHub squash merge) lands a tree no local gate saw; this is the probable cause of the stale catalog on main. Add a `post-merge` gate or require `just check` before each tag, and record it as a decision (no CI, ADR 0027) |
| C4 | Blueprint reports hook anti-patterns as findings with a fix: tests in `pre-commit`; the gate duplicated in `pre-push` and by hand; `core.hooksPath` taken by another tool; a hook that cannot fail; shelf-source guard living outside the repo (`SHELF_HOME` path lookups) |
| C5 | Box-wide test lock: one flock serialises whole pytest runs, so N sessions cost N times the gate. Candidates: core-aware slots, receipts so queued gates find a green result and skip. Measure on a loaded box before choosing |
| C6 | Gate budgets (60 s per step, 180 s total) stay, reported per step; whole-repo steps (`typecheck`, `arch`, `deps`, `blueprint`) cached by input fingerprint only if they are slow on a loaded box (3-7 s here) |

### D. Secret scanning

| item | what |
|---|---|
| D1 | A standard scanner (gitleaks or similar) over the changed range only: staged files in the commit hook, the diff range in the gate; a full scan on tag |
| D2 | The existing sops check (encrypted files really are sealed) stays |
| D3 | History: task-loop added gitleaks to its gate and reverted it the same day (d6e223b71, 739474b82); find out why before repeating it |

### E. Blueprint itself (skill and engine)

| item | what |
|---|---|
| E1 | Enforce outcomes, not command shapes: "the tests the change reaches ran green, or a receipt exists; a full run with coverage happens on tag", not "pytest inside `just check`" |
| E2 | Cut checkpoints no consumer needs. Costly demands seen: coverage tied to pytest-cov (a2kay override and shelf-2hl), `cli-parse` (two agent overrides and a code change in a2kay), `python-range` (a2kay override), Dockerfile/compose tool pile (a `images` gate step, removed once and re-added) |
| E3 | CORRECTED after reading `profile.py`: expiry is already enforced (`Override.problem`: an expired override stops excusing its checkpoint, and the report shows it). a2kay's `stack.python-uv.coverage` override expired 2026-11-11, so its blueprint step should now fail there, or a2kay pins an older shelf; not checked. The real gap is that nothing warns before the expiry |
| E4 | Reports are not committed on every run, only when the verdict changes. a2kay made 15+ blueprint commits in about 3 weeks |
| E5 | Incremental audit: fingerprint the inputs of each checkpoint, rerun only changed ones; split per-commit from audit-only checkpoints more strictly |
| E6 | `/blueprint` converge mode batches: at most one commit per shelf bump |
| E7 | A `blueprint` command that runs the changed-only tests, so one command does it |

### F. Ad hoc scripts become packages

| script today | copies | goes to |
|---|---|---|
| `tools/changed.py`, `tools/gate_state.py` | identical copies in `packages/blueprint/.../recipes/` and in consumers (a2kay has its own `gate_state.py`) | one package: selection, receipts, lock, gate state; a CLI over it |
| `tools/affected.py` | shelf only | same package; the lock rule of A1 |
| `tools/preset_drift.py`, `tools/hooks/forbid-local-shelf-source.py` | consumers call them through `SHELF_HOME`, `../shelf` or `~/Workspaces/shelf` | a pinned dependency, so a consumer needs no shelf clone |
| `tools/size_caps.py`, `tools/arch_rules.py`, `tools/catalog.py`, `tools/blueprint_fitness.py` | shelf only | decide per script: generic means a package, shelf-specific stays |
| `recipes/check_coverage.py`, `check_dockerfile_pins.py`, `check_godot.py`, `unity_integrity.py` | copied into consumers | same rule |

Naming follows ADR 0015 (`any-<domain>`); the number and names of the packages is a design question.

### G. `justfile` consolidation

POC result (just 1.58.0, throwaway repo): `import 'base.just'` cannot override an imported recipe (redefinition is an error), but a
base recipe can depend on a recipe the repo must define (`lint: lint-extra`). A missing extension point fails
loudly at load. `mod` also works and lets a local recipe wrap the module's (`check: gate::check`). Recipe counts now:
shelf 25, a2kay 30, task-loop 8, ogy 4.

| item | what |
|---|---|
| G1 | Blueprint ships one base justfile; each repo imports it and defines only its named extension points and its own extra recipes |
| G2 | Blueprint checks the vendored base against the version it ships (hash), replacing the justfile part of `preset_drift.py` |
| G3 | Decide import vs `mod` (import keeps command names; `mod` namespaces them) |

### H. Consumers

| repo | state | work |
|---|---|---|
| a2kay | most converged; gate 125-153 s; owns a `gate_state.py` copy and shelf-path hook lookups; expired coverage override | replace copies with the package; flat gate to selected tests; keep `slow` marker and fake-models rule |
| task-loop | audit of 2026-11-06 (33 findings) never acted on; own selector and receipts are ahead of shelf's; vendors 22 shelf packages | extract what is better into the package (see section 3), then adopt it and drop its own copy |
| OGY | no blueprint, no hooks, no gate; `justfile` is 4 recipes (ruff, pytest) | first adoption: bootstrap through blueprint |

### I. Defects found on the way (fix independent of the design)

| defect | status |
|---|---|
| `main` red: stale `use-cases/README.md`, `ledger/README.md` | regenerated locally, not committed |
| 2 undeclared workspace imports (`mcp-bridge`, `mcp-call` tests of `async-scope`) | open |
| unexplained unselected blueprint failure under the `atomic-io` mutation (the test uses a temp repo; not reproduced) | open |
| `process-lock` flake | FIXED: `any-lease` tests leaked held leases into the process-wide registry; leak detector added |
| `any-lease` sigterm test flake | open, unreproduced (1 of 3 full runs once; 0 of 300 stress, 0 of 6 later full runs) |
| 2 undeclared workspace imports | FIXED (fitness test plus dev groups, uncommitted) |
| a2kay coverage override expired 2026-11-11 (enforcement exists; what a2kay's gate shows now was not checked) | consumer finding, not this session's task |

## 3. Open investigations

| question | state |
|---|---|
| Is task-loop's selector (file-level closure plus coupling rules, receipts) better than shelf's package selector, and which parts to extract | answered below, section 3.1 |
| Second hub mutation | not run |
| Does anything in the Mac-only slowdown remain after receipts (C5) | needs a loaded-box measurement |
| ADR conflicts: read `docs/adr/INDEX.md`; check 0004, 0006, 0015, 0023, 0024, 0027 | not done |

### 3.1 Task-loop selector against the shelf's (20 shelf commits; one read-only agent, not cross-checked by a second reader)

Where it lives: task-loop `main` no longer has `dev/affected.py` (deleted by 9e965b00b, #722); the last version is in history
before it and in the worktree `.worktrees/loop-f2943fed` at 5a940722b. Its design docs (`test-tiers.md`, `gate-host.md`,
`test-inner-loop.md`) are proposals, not decisions.

Ran, with its globals patched for the shelf layout (selector logic unmodified), lock and root `pyproject.toml` changes
dropped from both columns, shelf fitness tests added to both. Repo has about 321 to 337 test files.

| selector | median test files selected | max |
|---|---|---|
| Shelf package selector | 34.5 | 52 |
| Task-loop file-level closure, as is | 63.5 | 80 |
| Task-loop closure with its "strings" rule off | 33.5 | 50 |

- The strings rule (a file whose string constants name a changed file's basename depends on it) adds about 30 files to every
  commit, because `README.md`, `pyproject.toml` and `__init__.py` appear as strings in about 30 test files across 79 packages. Basenames
  are not unique in a many-package workspace: do not extract that rule as written.
- Without it, file-level closure is the same size as the package selector or smaller by 0 to 2 files. Shelf commits change
  src, tests, README and pyproject of one package together, so file granularity buys almost nothing here. Single-file edits were
  not measured.

Better in task-loop (read from code): receipts keyed on each test's own closure bytes, which survive base moves (shelf keys on the
whole package plus its dependencies); coupling rules for conftest, data directories, discovery and deleted files (shelf sends the
unknown to everything); runner hygiene (hang guards of 3600 s wall and 600 s idle, worker cap = min(free cpus, RAM/2 GB,
ceil(tests/150), 4), isolated HOME, `quarantine` lane, `serial` tests apart, "selection reaches too far" alarm, which only prints);
`reach.py`.

Worse or unusable here: the strings rule; hard-coded layout; a whole-repo AST parse every run; public-surface propagation needs
`api.py` files; the green ledger is off by default and lives in `~/.cache`.

Extraction candidates, by certainty:

| # | what | note |
|---|---|---|
| 1 | Run guard: idle and wall limits, `nice`, worker cap, `quarantine` and `serial` lanes, wide-selection alarm (about 100 lines) | independent of selection, cheapest and most certain win |
| 2 | Receipt key plus ledger (about 80 lines, stdlib) | biggest win for repeat runs; needs a closure function, so depends on #3 or on the package-grain key |
| 3 | AST import graph and closure (46 lines), possibly in `py-symbols` or `test-reach` | only if single-file precision matters; the 20 commits say it barely does |
| 4 | Conftest and data-directory rules, with unique-path matching | small |

## 4. Process

Two or three missions (test loop and gate; blueprint outcome contracts; scripts into packages plus `justfile` base), each with its ADRs and bd issues carrying acceptance criteria. No backward compatibility: consumers are migrated, not shimmed.
