# Testing

Stack-neutral doctrine. The stack file names the tools.

## Principles

| rule | why |
|---|---|
| **The planner states the acceptance as scenarios; the writer implements them.** Scenario text (Given/When/Then, tagged by layer) comes with the bead; the writer writes the step code, then the feature code. | A writer who invents the tests also invents what "done" means |
| **Scenario first, at the public surface.** Write the behaviour as a scenario an actor would state (a user task, a request, a command) and run it through the real surface, in process. | In one codebase most closed bugs were workflow-shaped; unit tests stayed green through them |
| **Test at the highest level that can observe the behaviour.** | Lowest-convenient-level tests let sibling paths break later |
| **Few unit tests.** Only for one function's own rule: a parser edge, a refused value, a table of shapes. Write them as tables from the start. | Test count does not measure complexity; duplicates assert one rule many times |
| **Extend, do not add.** Add to the goal's existing scenario file or the module's test file; a new file needs a new goal or module. Never name a file after a bead, fix or change. | A file named after a change has no home for the next change |
| **A bug's regression test is a scenario** in its goal, covering every sibling path that takes the broken input, tagged with the bead id. | A narrow fix test pins one path |
| **Hermetic.** No real network, clock, home directory, git config, env var, model or OS service. Clear what the shell leaks, a git hook's `GIT_DIR` and `GIT_INDEX_FILE` included; fake at the process boundary, not past the code under test. | Local config makes tests pass here and fail elsewhere; shelf 2026-10: under a pre-push hook in a worktree, tests' `git -C <tmp>` rewrote the repo's own files and config |
| **Parallel-safe.** Each test owns its temp directory, port 0, its own state. No test needs another to run first. An address where nothing answers is held for the test (a bound socket that never listens), never probed and freed: a parallel test takes the freed port. | Serial tests are slow and order-dependent; a2kay 2026-10: a freed "unreachable" port got a parallel scenario's server, whose 401 read as an auth failure |
| **No retries, no `sleep` for sync.** A flaky test is fixed or deleted; wait on a condition. | A retry hides the bug that made it flaky |
| **Real thing in a lane, not instead.** A costly real dependency (git, database, model) gets contract tests proving the fake matches it. | An unchecked fake drifts |
| **A guard is seen red before it is trusted.** Break the code, watch the test fail, restore. | A test that cannot fail guards nothing |

## Where a test goes

| the behaviour is | the test is | it goes in |
|---|---|---|
| something an actor does or sees | a scenario | `{{scenario_dir}}` |
| one function's logic or a single-call rule | a unit test, table-style | `{{unit_dir}}`, mirroring the source path |
| a shelf package's own contract | that package's tests, in the shelf | never here; one wiring scenario here |
| an architecture rule | the architecture check ([architecture.md](architecture.md)) | `{{architecture_dir}}` |

## Slow tests

A test that costs seconds (a real build, a wheel, a browser) carries the `slow` marker; the per-commit pass leaves it out, and a second pass runs it only for a suite whose key changed since it last passed (editing the slow test, or code it reaches; a docs-only change runs none). The release run keeps it always.

| run | what runs | how |
|---|---|---|
| `just check` | every test but `slow`; plus the `slow` tests of each suite whose key changed since they last passed | `[tool.blueprint.test] marks = "not slow"` in `pyproject.toml` (never in pytest's `addopts`: `check-all` would skip them too) |
| `just check-all` | every test, `slow` too, with the coverage floor | `test-all` ignores `marks` |
| only the slow ones | `just test-all -m slow` (floor off: a partial run cannot meet a whole-repo floor) | arguments go to pytest |
| a name | `just test -k name`, `just test -m "not net"` | the later `-m` wins over the configured one |

`test` and `test-all` take pytest's arguments. A run with arguments is an override and writes **no receipts**: a receipt says "this unit
passed on this input", and an override ran a different set, so a later plain run would skip a unit nobody ran in full.

## Do not

- Pin a test to private structure: a refactor with no behaviour change must not break tests.
- Snapshot a whole transcript; an agent re-approves a diff it has not read.
- Delete tests by count or coverage alone; delete only with proof (a mutation run) that they guard nothing.
- Assert one rule at several layers.
- Weaken a test to pass. Fix the code.

## Bug workflow

1. Reproduce as a failing scenario. 2. See it red. 3. Fix. 4. See it green. 5. Run `just check`.
