# Agentic delivery: how agents build, test and gate a repo

The doctrine for a repo where coding agents do most of the work: who does what, which tests exist, which run when,
how fast the gate must be, and how review and landing work. Distilled from task-loop, delegate, shelf and lifesim,
2026-10 (studies in `~/Documents/Drop/arch-study-1025/`: 82, 88, 90, 91, 93, 94). Stack-neutral; the testing
basics it builds on are [docs/agents/testing.md](../../docs/agents/testing.md).

**Use it as an audit.** Each row is a rule, the evidence that made it a rule, and a check. Judge every row ✅ / ❌ /
untested with one line of evidence (`path:line`, a command and its output, a number). No row is "partly"; a row
that does not apply says why. Write the result to `docs/blueprint/agentic-delivery.md` in the audited repo, ❌ rows
first, each with its fix; the fixes become beads.

## 1. Roles and models

| # | rule | why | check |
|---|---|---|---|
| R1 | Agents assume instead of asking; each assumption is a typed record (task, step, text, reversible y/n). They ask only when the step cannot be undone. Never a timed auto-default. | Asks stalled tasks for hours, parked or paused with nobody reading them (lifesim, 2026-10) | asks in the last 20 tasks: each one is irreversible |
| R2 | The owner reads assumptions only when a later failure traces back to one; the dashboard shows a count. | Nobody reads a list of 200 assumptions | the failure report links its assumption |
| R3 | A structural change (rewrite, move, new layer) is built by strong agents in worktrees, one release each, never by the unattended loop. | A cheap writer on a 400-line structural move makes a second god object | the rewrite's commits come from supervised sessions |
| R4 | The unattended loop gets test-only, tooling and feature tasks whose files the rewrite does not touch. Tasks that touch files being rewritten wait (label `after-rewrite`). | Every line added to a file being rewritten is moved twice | open loop tasks vs the rewrite's file list |
| R5 | One agent per worktree, on its own branch; the main checkout is the owner's. | A commit hook stashes uncommitted edits; a second agent's write in the same folder is lost (shelf ADR 0019) | `git worktree list`; no agent edits in the main checkout |
| R6 | Cheapest capable model per role; the most expensive model never runs in the loop. A same-family reviewer is allowed only when it is the only lane up. | Review by the writer's family misses the writer's blind spots; top-tier models in a loop burn the quota | the routing table; the review log's families |

## 2. Agent context

| # | rule | why | check |
|---|---|---|---|
| C1 | AGENTS.md holds only facts an agent cannot work out from the code: where things live (folders, not files), the commands to run, the mistakes to avoid. | Agents re-found paths and commands each session; the owner's diagnosis of long sessions (not measured) | every line: could `ls` or `grep` answer it? then delete it |
| C2 | Harness- and model-specific files (`claude.md`, `codex.md`) load on demand only. | Loading every harness's file costs every session tokens for nothing | the root file links them by trigger |
| C3 | Early development states it: "no backward compatibility, nothing is precious (code, saves, screenshots)". | Agents spend tokens on shims, migrations and old-save corpora nobody needs | the line is in AGENTS.md |
| C4 | Prompts send what the agent needs inline (the current stage's diff up to ~24 KB, the spec, the check results); paths and stats only on overflow. | File dumps were 37% of tokens, base context 30% (study 29) | the prompt builder's caps |

## 3. Acceptance and test layers

| # | rule | why | check |
|---|---|---|---|
| T1 | The planner writes acceptance as Gherkin scenarios, as text in the task, not as test code. The writer implements each scenario as one test. A BDD runner is optional; a plain test per scenario is enough. | Acceptance an agent cannot map to a test is unverifiable; free-written unit tests pile up without pinning behaviour | each closed task: every scenario maps to one test |
| T2 | Every test carries one layer tag: **@domain** (in memory; no files, no processes, no network), **@contract** (one shared suite run against the real adapter and its fake), **@smoke** (one full real run per feature). A framework adds its own (lifesim: `@sim` .NET only, `@look` one behaviour in the engine, `@smoke` the full game). | Without layers every test drifts toward a full real run, the slowest kind | untagged tests = 0 |
| T3 | Domain code does IO only through ports (Git, task store, checks, delegate) and typed stores, each with an in-memory fake in the port's own package. No filesystem-mocking library. | Patching builtins hides where IO happens; a port names it | a rule test: no `tempfile` / `subprocess` import under `tests/domain/**` |
| T4 | Every fake is pinned by the @contract suite the real adapter also passes. | An unchecked fake drifts (shelf git-porcelain: 74 scenarios, run against real git and FakeGit) | each fake has its contract suite |
| T5 | The writer does not free-write unit tests. Unit tests exist for one function's rule (tables), property tests for maths. Behavioural tests stay; tests that pin internals go. | Test count is not coverage of behaviour; pinned internals break on every refactor | sample 20 new tests: each names a behaviour |
| T6 | Coverage floors stay low (line 75, diff 60, no branch floor): a backstop against untested code, never a target. | 92/90 floors once drove a repo to ~4,000 slow tests | the floor values in the gate |

## 4. Test count and cost

Measured on task-loop (2026-10-27): the suite was not full of redundant behaviours, it was full of redundant cost.
552 engine tests: 5 deletable, 75 removable as functions, while 18% of all CPU went to one `setUp` and ~150 process
starts per test.

| # | rule | why | check |
|---|---|---|---|
| K1 | A test that checks a pure function calls it directly; it never runs the whole engine to observe one value. | 38 tests ran a full engine for a pure function (study 91) | grep full-run helpers in tests whose assertion reads one function's result |
| K2 | One happy-path @smoke per feature; facets of that run are assertions on it, not separate runs. | 17 tests ran the identical happy run to read one facet each | count identical run setups |
| K3 | Expensive fixtures (a repo, a database) are built once per process and copied per test. | Copying a template repo instead of 5 git calls saved 348 s of 1,930 | `setUp` spawns no process |
| K4 | Cases of one rule are rows of one table test, not separate tests. | 62 tests merged into 19 tables, no behaviour lost | — |
| K5 | Count processes started, not seconds, when a test must bound cost. | Wall-clock assertions failed on every loaded run (task-loop selftest, 10 s limit) | no `assert elapsed <` in tests |

## 5. Test radius: what runs when

| # | rule | why | check |
|---|---|---|---|
| S1 | The dev loop runs @domain always (it is seconds), and @contract/@smoke selected by the change. | Full suites on every edit made the writer wait 7-15 min per round | the dev command's selection |
| S2 | Selection is derived from the import graph (a test module's static import closure ∩ changed modules), never from a hand table. It needs a no-lazy-import rule so the static closure is the runtime closure. | A hand map is a second copy of the graph and drifts | the selector reads the same graph as the layer rule |
| S3 | Any change to a non-code input (goldens, fixtures, config, vendored code) runs FULL. @smoke always runs. | These have no import edge | selector tests for each input kind |
| S4 | The release gate ignores the selector and runs everything. A shadow replay of recent landings turns the selector off on its first miss. | Selection errors must not reach main | the release command; the replay log |
| S5 | Build the selector last, after the code has layers; while hub files hold everything, FULL is the right answer. | 100% selection is correct for a flat codebase (study 93) | — |
| S6 | Fix rounds re-run only what the diff since the last green round reaches; a conflict fix runs conflict markers and build, not every stage's checks. | Conflict fixes re-ran every check: ~284 min a week | the fix round's check list |

## 6. Speed on the machine

| # | rule | why | check |
|---|---|---|---|
| M1 | Measure the machine's per-operation tax before optimising code: file write+close, first read, process start. | An endpoint scanner (MS Defender, MDM, no exclusions possible) made write+close 1-14 ms vs 0.05, a process start 24-32 ms vs 0.8-9; the suite was O(tests × processes × files) | a recorded benchmark per machine |
| M2 | Heavy check commands (tests, builds) run in a Linux container on a clone on the container's own disk, never a bind mount. Fall back to the host when Docker is down. | 895 s host vs 122 s container; a bind mount is as slow as the host (192 s vs 184 s) | the gate command |
| M3 | The agent itself stays on the host; per stage, its checks may run elsewhere (a stage asks for a runner by plain label, `needs: {docker: true}`; the host is one runner). No affinity, taints or scoring. | Agent edits are tens of files; checks are the mass churn. Agent logins (Keychain) do not carry into containers | stage config names its needs |
| M4 | A framework that cannot run in the container stays on the host, measured not assumed. | Unity 6000.7 on Apple Silicon: no arm64 Linux editor, the amd64 editor crashes under Rosetta (study 94); `dotnet test` under emulation was slower (151 s vs 110 s) | a trial result per framework |
| M5 | Shard the suite on measured per-test durations (heaviest first onto the lightest shard, stable by name), refreshed by an explicit record command, not on every run. Unknown tests use a per-module estimate. | Count-based shards were 1.47x unbalanced, duration-based 1.19x | the splitter's input |
| M6 | Tests that race real processes or the clock run serially after the shards, each listed with its reason. | Under load they time out next to others | the serial list has a reason per entry |
| M7 | Keep log handles open; append, do not open-close per record. | Every close is a scan | grep `open(... "a")` inside loops |

## 7. Determinism

| # | rule | why | check |
|---|---|---|---|
| D1 | No retries and no `sleep` to sync; wait on a condition. A flaky test is fixed or deleted. | A retry hides the bug that made it flaky | grep retries in test helpers |
| D2 | Ids that name runs, dirs or checkpoints are unique beyond the clock's resolution. | A second-resolution run id let a fast rerun reuse the first run's checkpoint and skip the work; only the fast container gate exposed it | id generator test: two ids in one tick differ |
| D3 | A gate or check killed by a signal is a fault (retry or block), never "red tests". | A killed gate counted as red ran a needless fix round and closed the task blocked | exit < 0 maps to a fault |
| D4 | Kill only confirmed PIDs (process group, then proof of death); never by name or pattern. The process that starts a worker owns its death; `docker exec` forwards no signals, so container processes are killed through the runner. | Pattern kills hit other agents' processes; a lost signal left two writers in one tree | grep `pkill`, `killall` |
| D5 | Tests are hermetic: own HOME, temp dir, git config, no real network or OS service. | Local config makes tests pass here and fail elsewhere | the test base class |

## 8. Review

| # | rule | why | check |
|---|---|---|---|
| V1 | One reviewer, cheapest capable lane first; shape: diff + spec + check results, with a tool-call cap and a token cap. | One task (tl-7y6.1.1) spent 86 min in 7 reviews against 119 min of writing | the review prompt's inputs and caps |
| V2 | Every finding is typed: axis (spec / standards), severity, confidence, category, evidence (`file:line` plus a concrete failure scenario: inputs → wrong output). Only severity ≥ high, confidence ≥ likely, with a scenario, blocks; the rest are notes. | Untyped findings sent work back on notes that were not defects; the same task took 5 rounds | the review schema |
| V3 | The spec axis maps every acceptance scenario to its evidence; an unmapped scenario is a finding. | Guards against the reviewer missing what was never built | the review output lists the map |
| V4 | Mechanical diffs skip review deterministically: only when every changed path is docs, allow-listed config, a 100% rename, a formatter-only change or generated files. | Review of a rename costs a full review round | the skip rule's path list |
| V5 | A reviewer model earns its place on a replay of labelled send-backs (real defects per M tokens). | A cheap reviewer with many false positives costs more than a dear one | the eval result |

## 9. Gate and landing

| # | rule | why | check |
|---|---|---|---|
| G1 | The local gate is the only gate. CI is a non-blocking backstop after landing. | A blocking remote CI that is red on every OS blocks nothing useful and stalls everything | CI is not a required check |
| G2 | One command is the gate; landing holds a lock; the release suite runs on the rebased result before push. | Two loops race to land on one main; the race is tested with real processes (task-loop `test_race`) | the land lock and its test |
| G3 | A scanner of all history (secrets across every commit and branch) does not run in the gate. | 34 s per run for the same history every time | gate steps |
| G4 | Rebase at land, squashed to one commit; after a stop, squash the WIP commits and try a conflict fix before restarting the branch. | A merge gives the same conflicts; restarting loses work | the land path |
| G5 | Every run is classified against a failure taxonomy (MAST, arXiv 2503.13657) and the result is shown with the run. | Without a class per failure, the same failure repeats unnoticed | the run report has the class |

## 10. Running the audit

1. Read the repo's AGENTS.md, gate command, test tree, loop config and the last 20 closed tasks' records.
2. Judge each row in sections 1-9. A number beats a claim: count tests per layer, time the gate, count process starts in one @domain test.
3. Write `docs/blueprint/agentic-delivery.md` in the repo: ❌ rows first (rule id, evidence, fix), then untested, then ✅.
4. File one bead per ❌ fix. A rule that is wrong for this repo becomes a `blueprint lacks:` bead in the shelf, with the evidence, never an exception granted in chat.
