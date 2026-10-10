# Testing

Stack-neutral doctrine. The stack file names the tools.

## Principles

| rule | why |
|---|---|
| **Scenario first, at the public surface.** Write the behaviour as a scenario an actor would state (a user task, a request, a command) and run it through the real surface, in process. | In one codebase most closed bugs were workflow-shaped; unit tests stayed green through them |
| **Test at the highest level that can observe the behaviour.** | Lowest-convenient-level tests let sibling paths break later |
| **Few unit tests.** Only for one function's own rule: a parser edge, a refused value, a table of shapes. Write them as tables from the start. | Test count does not measure complexity; duplicates assert one rule many times |
| **Extend, do not add.** Add to the goal's existing scenario file or the module's test file; a new file needs a new goal or module. Never name a file after a bead, fix or change. | A file named after a change has no home for the next change |
| **A bug's regression test is a scenario** in its goal, covering every sibling path that takes the broken input, tagged with the bead id. | A narrow fix test pins one path |
| **Hermetic.** No real network, clock, home directory, git config, env var, model or OS service. Clear what the shell leaks; fake at the process boundary, not past the code under test. | Local config makes tests pass here and fail elsewhere |
| **Parallel-safe.** Each test owns its temp directory, port 0, its own state. No test needs another to run first. | Serial tests are slow and order-dependent |
| **No retries, no `sleep` for sync.** A flaky test is fixed or deleted; wait on a condition. | A retry hides the bug that made it flaky |
| **Real thing in a lane, not instead.** A costly real dependency (git, database, model) gets contract tests proving the fake matches it. | An unchecked fake drifts |
| **A guard is seen red before it is trusted.** Break the code, watch the test fail, restore. | A test that cannot fail guards nothing |

## Where a test goes

| the behaviour is | the test is | it goes in |
|---|---|---|
| something an actor does or sees | a scenario | `packages/<name>/tests/features/` |
| one function's logic or a single-call rule | a unit test, table-style | `packages/<name>/tests/`, mirroring the source path |
| a shelf package's own contract | that package's tests, in the shelf | never here; one wiring scenario here |
| an architecture rule | the architecture check ([architecture.md](architecture.md)) | `tests/` |

## Do not

- Pin a test to private structure: a refactor with no behaviour change must not break tests.
- Snapshot a whole transcript; an agent re-approves a diff it has not read.
- Delete tests by count or coverage alone; delete only with proof (a mutation run) that they guard nothing.
- Assert one rule at several layers.
- Weaken a test to pass. Fix the code.

## Bug workflow

1. Reproduce as a failing scenario. 2. See it red. 3. Fix. 4. See it green. 5. Run `make check`.
