# Testing strategy — lessons from a2kay (reference for the blueprint skill)

Source repo: `~/Workspaces/a2kay`, read 2026-10-10. Every number below is quoted from a source; the
source is named next to it. Paths are relative to the a2kay repo.

**Provenance tags** (the material is split across unmerged branches; a skill must not present a spike
as settled practice):

| tag | meaning |
|---|---|
| `[bdd]` | committed on `spike/pytest-bdd` (3aebc79) |
| `[lin]` | committed on `spike/lineage` only (2b9656a) |
| `[mzfh]` | committed on `spike/mzfh` only (d751d3e) |
| `[wt]` | uncommitted, in the `.claude/worktrees/bdd-spike` working tree only |
| `[hand]` | handoff/transcript only; not in any repo doc |

Shorthand for sources: TS = `docs/research/testing-strategy.md`; PREP = `docs/research/usecase-test-prep.md`;
DES = `openspec/changes/use-case-layer/design.md`; TASKS = `…/tasks.md`; LEDGER = `docs/research/unit-prune-ledger.md`;
PM = `docs/research/test-pruning-method.md`; MC = `docs/research/test-merge-and-complexity.md`;
SO = `docs/research/test-shape-and-ownership.md`.

## 0. The failure this prevents (stack-neutral)

| symptom | number | source |
|---|---|---|
| Workflows broke while unit tests stayed green | 39 of 71 closed bugs workflow-shaped; a test found 1 of 71 (a flaky one); real use 38, review 30 | TS §1–2 |
| Narrow fix test pins one path, sibling path breaks later | 5 recurrence pairs (e.g. padded id fixed in graph store, graph verbs broke 5 days later) | TS §2.1 |
| Suite tests functions, not journeys | 2 of 13 journeys had a client-level test; of 24 traced spec scenarios, 14 ran at core/service, 1 at MCP, 1 at CLI | TS §3 |
| Agents add files instead of extending | 67% of `feat` commits created a test file; 24 files named after a change; 27 files never edited again | TS §4.3 |
| Same rule asserted at several layers | 8 duplicate clusters (e.g. stale-version refusal: 10 files, 11 tests) | TS §4.2 |
| Shared fixtures bypassed | `vault` fixture used by 6 tests while 1,294 took `tmp_path` and built their own; `_setup` redefined in 38 files | TS §4.1 |
| Test count does not measure complexity | Spearman tests-by-import vs cyclomatic 0.41; LOC vs cc 0.86 | TS §8 |

## 1. Test layers and placement

| layer | what it tests | drives | in a2kay |
|---|---|---|---|
| **Use case** (primary) | a goal an actor would state as a task | the actor's real surface, in process: in-memory MCP client, in-process CLI, job runtime | `tests/usecases/<domain>/<goal>.feature` `[bdd]` |
| **Unit** | one function's rule, or a single-call rule (enum refused, parser edge) | the function | `tests/<src path>/test_<module>.py` `[bdd]` |
| **Contract** (adapter) | a costly real dependency behaves as the fake assumes | the real thing (git) | designed ~15-test adapter suite not built (TASKS 2.10c); the existing history tier (sync, LFS, merge lock) already runs on real git, ~1,300 s = 35% of suite time (PREP §8) |
| **Vendor-real / costly lane** | real model, real ports, child processes, real time, launchd | marked `model net subprocess git slow macos` | markers in `pyproject.toml` `[bdd]`; "markers name slices of `make check`; they never exclude from it" (ADR 0044 §6) |
| **Shared-package contract** | a shelf package's own behaviour | that package's tests, in the shelf | app keeps one wiring scenario per package (ADR 0044, DES §4) |

Why use cases first: TS §2 judged a use-case test would catch 24 yes / 14 maybe / 1 no of the 39 workflow
bugs, but only 1 yes of the 20 unit-shaped bugs. "Use-case tests are not a replacement for unit tests.
They are the missing layer for the bigger class of bugs." (TS §2). Rejected alternatives with verdicts:
plain pytest per behaviour ❌ (produced the 38 `_setup` copies), executing spec scenarios directly ❌,
LLM agent evals as gate ❌ / ✅ for discovery (cold-agent runs found 21 bugs), whole-transcript snapshots ❌
(an agent re-approves a diff it has not read) — ADR 0044 Alternatives.

**Placement table, verbatim from AGENTS.md §2** `[bdd]`:

| the behaviour is… | the test is… | it goes in |
|---|---|---|
| something an actor does or sees: an agent over MCP, the owner at the CLI/daemon, a job | a Gherkin scenario written from `tests/usecases/STEPS.md` | `tests/usecases/<domain>/<goal>.feature`. The domain is the one `tests/usecases/README.md` maps the first `@spec:` tag to. |
| one function's logic, or a single-call rule (an enum refused, a parser edge) | a plain pytest unit test | `tests/<src path>/test_<module>.py`, mirroring `src/a2kay/<src path>/<module>.py` |
| a shelf package's own contract | that package's tests | the shelf repo, never a2kay. a2kay only checks it is wired in, with one scenario. |

Rules around the table (AGENTS.md §2 `[bdd]`), each with its reason:
- Test at **the highest level that can observe the behaviour**. Why: of 24 traced scenarios, most were
  tested "at the lowest convenient level" (TS §3) and the recurrence pairs slipped through there (TS §2.1).
- **Extend the existing goal's `.feature` or the module's `test_<module>.py`; a new file needs a new goal or
  module; never name a file after a change, bead or fix.** Why: "A file named after a change has no natural
  home for the next change's test, so the next change makes its own file" (TS §4.3).
- **A workflow bug's regression test is a scenario in its goal's feature, tagged `@bug:<id>`, covering the
  sibling paths** (every verb that takes the broken input). Why: the 5 recurrence pairs (TS §2.1).
- **Lineage rule** `[lin]` (AGENTS.md on `spike/lineage` only): before changing a function, read its row in
  `.lineage/ranking.md` (tests aimed at it, fan-out, complexity); a function many tests aim at gets its new
  test as a table row, not a new function; after the change run `make change-report` and justify or undo
  growth.
- Unit tests mirror a **module inside its domain**, never a use case. Why: only 73 of 1,323 act-targeted unit
  tests (5.5%) aim at a function exactly one feature reaches; create / find-then-read / attach reach 0 of 70,
  2 of 127, 0 of 110 functions on their own (SO §2). The mirror rule was followed by only 46 of 181 files,
  so it needs a ratchet check, not a sentence (MC §2.1, §2.3; ratchet not built).

## 2. Gherkin conventions (Python-specific tool: pytest-bdd `>=8,<9`)

Pin `<9`: 9.0.0 (2026-09-30) drops `__scenario__` (PREP §1). Stack-neutral lessons below; the tool is not.

- **One goal = one `.feature` file**; main success scenario first, extensions after (Cockburn). A new case for
  an existing goal goes into that file (`tests/usecases/README.md`).
- **Folders = a fixed set of noun domains**, chosen by the goal's **first `@spec:<capability>` tag**; verbs only
  in file names (`find_then_read`). Why: "the next writer… must be able to work out where a behaviour lives
  from the behaviour alone" (DES §1). Measured alternatives (ADR 0044/0045): actor folders ❌ (one folder
  would hold most of the suite), one folder per capability (59) ❌, free product-area names ❌ (two writers
  name the same area differently), activity names ❌ (as code `write` would hold `read`; 45 edges find→write).
  Noun split kept the most import edges inside a group: 7 domains 52% vs 10 domains 44% vs layer packages 34%
  (ADR 0045).
- **One step vocabulary file** (`STEPS.md`), phrases used verbatim, checked by script. Why: four parallel
  writers proposed **201 phrases for 212 scenarios**; one merge pass brought it to **68** (TS §10, ADR 0044).
  "The step library does not prevent sprawl by itself. A fixed vocabulary file and a checker… do." A new phrase
  needs two uses and a failed attempt to parameterize an existing one (STEPS.md "Rules for adding a step").
  Constrain any parameter that opens a phrase or sits next to another to a fixed value set, so no phrase
  swallows another (STEPS.md rule 2).
- **Generic steps carry most scenarios** (DES §2): a tool call with a JSON docstring
  (`{actor} calls "{tool}" with:`, shelf `mcp_steps.steps`), a CLI run (`the owner runs "{command}"`), a
  dotted-path assertion (`the {subject} {op} "{value}"`, `the {subject} matches:` subset match). Domain
  phrases stay only where they make the scenario read as a use case and are used ≥2 times.
- **`Then` asserts only what the actor sees** (results, refusals, output, files they read), never internal
  stores (STEPS.md; ADR 0044 §3).
- **Tags** (README, `bdd-tags` plugin, ADR 0044 §6):
  | tag | effect |
  |---|---|
  | `@spec:<cap>`, `@bug:<id>` | traceability only, swallowed (not markers) |
  | `@known_bug:<id>` | strict xfail: turns red the day the bug is fixed, then the tag must go |
  | `@pending` | collected and skipped; a missing step in an untagged scenario **fails** (a typo cannot become a permanent skip — ADR 0044 alternatives) |
  | `@agent @owner @scheduler` | actor markers |
  | `@net @subprocess @git @slow @model @macos` | cost markers; select slices, never exclude from the gate |
  | `@expects_refusal` | opts out of the history invariant (§3) |
- **Never weaken a scenario to make it pass**; use `@known_bug` (README).
- **A bug found while writing a scenario is filed at once** and the scenario carries the tag. Writing the
  inventory against live behaviour found 8 bugs (TS §10; ADR 0044 Consequences).
- **Composition = shared Givens + one world fixture, not scenario chaining.** pytest-bdd has no "include
  scenario"; `Background` in 38 of 39 features; the scenario world is a plain fixture a unit test can request
  (SO §1.4). Scenario Outlines: 0 uses; use them only where 3+ scenarios differ in one value (SO §1.4).
- pytest-bdd traps (PREP §1, README): one unregistered tag fails collection of the whole domain module; a
  duplicate scenario name in one file **silently drops** the earlier one → names unique per domain.
- Each domain folder is collected by one `test_<domain>.py` containing `scenarios("<domain>")`, so every new
  feature is collected immediately (README).
- Guards planned but **not built** (TASKS 2.12): every `@spec` names a capability; folder matches domain;
  every step matches STEPS.md; unique scenario names per domain; no `@pending` whose steps all exist.

Folder tree `[bdd]`:
```
tests/usecases/
  README.md            # domain table: capability -> folder; tag rules
  STEPS.md             # the vocabulary (Given / When / Then tables, parameter value sets)
  conftest.py          # world (Agent), placeholders, invariant hook
  steps/{world,calls,assertions,owner,serving,jobs,history,supervisor}.py
  test_<domain>.py     # scenarios("<domain>")  x7
  entities/ index/ attachments/ jobs/ history/ owner/ surface/   # 39 .feature files
```

Example (abridged from `tests/usecases/entities/fix_a_stale_write.feature` `[bdd]`):
```gherkin
@agent @spec:optimistic-concurrency @spec:self-correcting-errors @spec:entity-crud
Feature: Fix a stale write
  Background:
    Given a fresh vault served over MCP
    And a project "Harbor migration" with id "7" and body:
      """
      ## Plan
      Move the harbor.
      """

  Scenario: A stale update is refused with the current entity and succeeds when re-applied onto it
    Given the agent has read "project/7"
    And someone else retitles "project/7" to "Harbor move"
    When the agent calls "update" with:
      """
      {"ref": "project/7", "version": "$version_read", "fields": {"horizon": "ongoing"}}
      """
    Then the call is refused with "version_conflict"
    When the agent calls "update" with:
      """
      {"ref": "project/7", "version": "$refusal_version", "fields": {"horizon": "ongoing"}}
      """
    Then the entity "project/7" matches:
      """
      {"fields": {"horizon": "ongoing"}}
      """
```
Fixtures use fictional names only (`Harbor migration`, `Acme`); never copy examples from specs or real data
(README; AGENTS.md §2 "No real data in the repo — ever").

## 3. Isolation

**Hermetic autouse pieces in `tests/conftest.py`** `[bdd]` (generic doubles live in shelf `testing` modules):

| piece | why (what broke / would break without it) |
|---|---|
| clear every app-prefixed env var (`A2KAY_*`) | the shell that started the run leaks config into tests (DES §3 item 1) |
| tmp `HOME` and app config home | the first CLI/owner scenario reads and writes the real `~/.config/a2kay/default` and can kickstart the real login item (DES §3) |
| git configured **through the environment** (`GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_COUNT` with `maintenance.auto=false`, `gc.auto=0`, `core.hooksPath=/dev/null`, `commit.gpgSign=false`, `init.templateDir=`, fixed identity) — `git_porcelain.testing.apply_hermetic_env` | picks up the user's hooks and gpgsign (DES §3); env reaches the app's own git calls too (PREP §9); `maintenance.auto` otherwise starts a 2nd process per commit (PREP §9) |
| hermetic LLM env (provider keys removed) — `anyllm.testing` | `profile_regen` called the real `claude` CLI (DES §3 item 2) |
| refusing fake for OS services first on `PATH` (`launchctl`) — `launchd_agent.testing` | no test reaches launchd; with tmp HOME makes every scenario parallel-safe: "Scenarios that must run serially: 0" (PREP §2) |
| fake embedder (hash vector), no reranker, no tokenizer load — unless marked `model` | a server alive past the 30 s settle loads the real model (`a2kay-kg4o`); 20 model loads cost ~100–150 cpu-s (DES §3, PREP §4) |
| model cache path read **before** HOME moves (`HF_HOME`) | `model` tests need the real cache |
| attach allow-list = tmp root | tests stage files in their tmp folders |

Ordering rule: a test that sets one of these itself wins (its `monkeypatch` runs after). A switch the scrub
would clear must be **read at import time** (`_ALL_GIT` in `tests/usecases/conftest.py`: "the suite's hermetic
env clears every `A2KAY_*` before a test runs").

**Fake at the process boundary, not the port** (DES §3a-revised; PREP §13, a second-model review):
- Bug `a2kay-oub` lived in `_screen`, a path rule that runs **before** git. A port fake (`NullHistory`) skips it.
- So `RecordingHistory` (`tests/_history.py` `[bdd]`) subclasses the production `GitHistory` and replaces only
  `_commit_paths`; the refuse-list, LFS decision, trailers and lock run on every write.
- **Autouse invariant after every passing scenario**: nothing refused, nothing held back, not degraded, every
  touched path in exactly one recorded commit (`_check_history` `[bdd]`). Opt-out tag `@expects_refusal`.
- Path-shape tables in plain unit tests over every shape a verb emits — "No architecture fixes an absent
  example: `oub` escaped because no scenario named a note `token`" (PREP §13). These tables were exempted from
  mutation pruning (TASKS 3b.4; LEDGER "Pure-logic cut").
- General verdicts for any costly layer (PREP §13): swap the engine (Postgres→SQLite) ❌ drift; tune the real
  engine first ✅; a fake checked by the same contract suite as the real layer ✅; record & replay ✅ external
  APIs / ❌ stateful local layer; one real test per domain = smoke only.
- In-memory store instead of the real one ❌: it builds no graph or search index (DES §3b). pyfakefs / fake
  git ❌: git is a separate process and sqlite's C layer bypasses Python's `os` (PREP §9).

**Real-git lane, in the gate** `[bdd]`:
- Every scenario's vault is a git repo as in production; plain vault + recording history only for the inner
  loop (`make test-usecases`). `make test` sets `A2KAY_USECASES_GIT=1`.
- Cost: **56 s vs 39 s plain for 205 scenarios (+17 s)** (DES §3a-revised item 6; Makefile comment).
- Nightly-only run ❌: "a break would surface a day after the commit that caused it" (DES §3a-revised).
  Stale: `tests/usecases/conftest.py` docstrings still say "the nightly matrix" — conflicts with the Makefile.
- Why git by default: with history off, "a write that breaks only when a commit follows it would pass the
  whole layer" — the "two backends behind one surface" drift (DES §3a).

**Still open** (do not present as solved): `wait_until` and a clock seam (TASKS 2.11); fake LLM provider and
`xdist_group("model")` (2.4); the adapter contract suite and `RecordingHistory` gate wiring (2.10c, partly
built); ports — the rule is `port=0` and a known-dead port for "no server" probes (DES §3 item 7), but
`Agent.port` still **binds port 0 then releases it**, so another process can take it first (PREP §12c end;
`tests/usecases/conftest.py` `Agent.port`).

## 4. Unit tests

| rule | why / evidence | source |
|---|---|---|
| Unit tests are for single-function rules (AGENTS §2). Proposed, not adopted: a unit test aimed at a verb a scenario reaches is a scenario row, enforced by a ratchet (not built) | 593 unit tests call a router/app/entrypoint function a scenario also reaches; one in three unit tests targets a verb | MC §2.1–2.3 |
| Write them as tables (`parametrize`) from the start | B pass: 125 functions in 55 files merged into tables, 0 items lost; tables **add** lines (8,312 → 8,449) — merging cuts functions, not items or lines | LEDGER "B"; MC §1.1 |
| Combinatorial matrix → pairwise covering array | 720-item find matrix (6 axes) → 20 pairwise rows; the 20 rows kill 1,869 of the 1,888 mutants the 720 kill, the other 19 are killed by the kept selection; 738 → 38 items | LEDGER "i0" |
| Delete only with mutation proof, never by count or coverage | coverage left 447 of 524 (85%) undecided (LEDGER first pass); of the 61 candidates actually attempted, mutation kept 4 (PM §4); 3 clusters lost mutants on the first run — that is how the keepers were found | LEDGER, PM §4 |
| Measure shrink as functions, lines **and** items | third pass: −213 functions, −1,066 lines, but only −88 items | LEDGER third pass |
| Judgement on top of mutation: keep what mutmut cannot see | snapshots, schema names, decorator args, docstrings, YAML, source scans, security/privacy boundaries, process and git boundaries, documented tables | LEDGER third pass "Method" |

Prune results (LEDGER): pass 1 (entities + 8 clusters) 401 → 344 items, −9.6 s; pass 2 (index) −751 items,
~−21 s; pass 3 (5 domains, 444 candidates → 161 deletable, 88 deleted); pure-logic cut −22 functions,
−41 items. Expected size elsewhere: "roughly 5–10% of the ~3,300 unit tests" (PM §4).

**Lineage ranking** (MC §2; `scripts/lineage/` `[lin]`):
- Act target = the last product call before the first assert (Arrange-Act-Assert). First rule ("last call by
  bare name") was **wrong 176 of 464 times (38%)** on the top 11 (SO §3); getters and test-local name clashes
  (`_version`, 32) drew tests. Corrected rule (resolve calls through the test file's imports; follow a read-back
  to the earlier state-changing call) fixed 147 of 176; residual error ≤ ~9%; 1,274 of 1,629 tests get a target
  (MC §2.2a `[lin]`). Lesson: check a heuristic against a hand-read sample before ranking with it.
- Concentration: 32 functions are the act target of 711 tests (54%) (MC §2.2). `EntityRouter.create`, fan-out 24:
  105 tests by the first rule (MC §2.2), **134** by the corrected rule (generated `.lineage/ranking.md` in the
  lineage worktree — a build artefact, not a doc).
- What predicts test count: complexity barely — ρ(cc, tests reaching) **+0.10**, ρ(cc, survival rate) **+0.11**.
  Fan-out is not linearly correlated either (+0.16 vs act count) but is **concentrated**: the 14 functions with
  fan-out ≥ 15 (1% of functions) are the act target of 216 tests (16%) (MC verdict table, §3.3).
- High count has two opposite causes: god functions (only door to untested collaborators — wants a code split)
  and getters (how a test looks — wants nothing). "Count ranks attention; it does not rank redundancy" (SO §3.1).
- Index generated and git-ignored; committing it ❌ ("a merge-conflict generator"); per-test `target` markers ❌
  (1,765 hand annotations that drift) (MC §2.3).
- Per-change complexity check: **report, not gate**. Replayed on 30 commits it would have failed 7 of 16 code
  commits (44%); 5 of 19 flags were the helper extraction it asks for (MC §4.1 `[lin]`). Thresholds: cc rises
  and ends > 10; fan-out rises and ends > 12; IO kinds report-only (blind behind collaborators).

**Helper-smell classification** (SO §1.1; 616 file-local helpers, 3,964 lines; 325 helpers / 2,175 lines =
**55%** are symptoms):

| class | helpers / lines | fix |
|---|---|---|
| (a) awkward product API (e.g. a required constructor arg 75 of 124 calls pass identically) | 70 / 476 | change the product: give the arg its default (`AdminRouter` already did) |
| (a′) shared fixture exists, not used | 70 / 308 | use the fixture (`indirect` params) |
| (b) shared test tool missing or not imported | 35 / 272 | import / add it in the `testing` module of the package that owns the faked seam |
| (c) scenario fragment (seeds state through verbs or disk) | 129 / 1,077 | share the Given; expose the scenario world as a fixture |
| (d) legitimate space saving (data tables, extractors, assertion helpers, doubles of own ports) | 291 / 1,789 | keep |

Cross-cut: **91 helpers copy one that already exists** (≥245 lines); the shared `run` helper "existed as 28
byte-identical private copies before it existed once, and 21 came back" (SO §1.1). "No helpers" is the wrong
target; "no helper that seeds a vault, builds a router, or copies a shared one" is the right one (SO §1.5).
Clone-detector gates ❌: jscpd found 2.76% duplication, pylint 17 hits mostly import headers (MC §1.3).

## 5. Speed and the machine

Measure first. Every lever below came from a timed comparison; the cost was process starts, not the
framework.

| measurement | number | source |
|---|---|---|
| per process start, macOS host vs Linux container | ~25 ms vs ~1 ms ("macOS process start plus the endpoint-security scan") | PREP §9 |
| 105 git execs: host / container own FS / container tmpfs / bind mount | 2,590 / 110 / 80 / 1,120 ms | PREP §9 |
| full gate, host vs container | ~340 s vs 64 s | AGENTS.md §1, Makefile `[bdd]` |
| `make test` host vs `make test-container` | 337 s vs 56.5 s (6.0×) | PREP §10b |
| mutmut, one module | 770 s host vs 44–45 s container (17×) | PM §1.2 |
| one test file, host under load | wall 48 → 101 s at constant ~8.6 s CPU; sys 4.2 s host vs 0.3 s container | PM §1.1 |
| CPU of one full run | pytest ~1,281 cpu-s; Defender ~815 above idle; Fortinet ~122 | PREP §4 |
| same tests inside full run vs alone | 5–8× longer (`history_sync`: 575 s vs 103 s); 14 workers used 0.5–6 cores | PREP §8 |
| git forks per write, git vault | 11 → 5 after caching probes; ~10 forks dominate a scenario, MCP layer < 100 ms | PREP §7, §3 |
| eager CLI import | 2.6 s per subprocess call; 168 CLI calls: ~7.6 min subprocess vs ~37 s in process | PREP §2 |
| no bytecode cache (`PYTHONDONTWRITEBYTECODE=1` in agent envs) | `import a2kay.serve` 4.5 s vs 2.0 s | PREP §3 (Python-specific) |
| YAML re-parse per vault | 1,401 loads, 195 cpu-s (~15% of run) | PREP §4 |
| pytest-xdist on small selections | doubles wall (≈3.5 s per worker start); run < ~25 scenarios with `-n0` | DES §3b (Python) |
| coverage | adds 9%; not the lever | PREP §8 |
| pytest-testmon | ❌ ignores `.feature` edits | DES §3b |

Levers, stacked per scenario: 614–672 → 449 (cache build identity) → 336–371 (services off) → 289–316 (cache
`is_repo`) → 219–288 ms (ontology cache) (PREP §3).

**Container delegation** (Makefile `[bdd]`): `make check` runs `check-container` when Docker answers, the shelf
clone is found, `CI` is unset and no host override is set; otherwise `check-host`. Rules:
- The container is an accelerator, never a requirement; CI (already a container) runs in place — never nest.
- Code is **copied** into the image, never bind-mounted ("a bind mount brings the slow path back"); code is the
  last layer, so a rebuild after a code change is ~30 s (PREP §10b).
- Linux image traps found: no `/etc/mime.types` in `python:3.12-slim` → `.xlsx` refused (the shipped image had
  the bug); `RLIMIT_NPROC` counts threads on Linux; macOS `tar` adds `._*` files; a `chown -R` made an 11 GB
  image; lock pinned ~4 GB of CUDA wheels (PREP §10).
- One image tag (`a2kay-test`) for every worktree — parallel runs used each other's image (Makefile; session
  agent report). Fix not built: tag per worktree or run by image ID.

**Slots** `[mzfh]`: heavy container jobs (`check-container`, `test-container`, `prune`, image build included)
take one of `CONTAINER_SLOTS` (default 2) machine-wide slots via `scripts/container_slot.py`; waiters print who
holds the slots. No queue in CI or inside a container.

**flock, not lock files** `[mzfh]`: a slot is an exclusive `flock`, "the kernel releases it when the holder dies,
so a killed job never leaves a slot taken" (`container_slot.py`). Same pattern fixed a load-only bug:
`a2kay-mzfh` — the watcher's `git status` held `index.lock` while a verb committed; the verb gave up after three
tries and the file stayed untracked. Fix: one per-repo lock (thread lock + `flock` on `.git/a2kay-write.lock`)
(commit e383415). Lesson: bugs that appear only under load are real.

Machine-dependent bugs: `@known_bug:a2kay-azii` scenarios turned `XPASS(strict)` in the Linux container (the bug
was macOS-only) (PREP §10b). Prefer fixing; else tag per platform.

## 6. Mutation pipeline (Python-specific tools; the method is stack-neutral)

`make prune DOMAIN=<d>` → `scripts/prune/run.py` in the test image `[bdd]`; config `scripts/prune/domains.toml`
(domain → modules, `skip`, `exclude_marks`).

1. **contexts** — whole suite once with per-test coverage contexts; cached while `src/`+`tests/` unchanged.
2. **filter** — candidates: unit tests owned by the domain whose covered lines are all covered by scenarios or
   other unit tests. Coverage only scopes: it decides nothing ("covering a line is not checking it", PM §2);
   only 11% of `tests/core` were provably unique by coverage (PM §1.4).
3. **generate** — mutmut makes mutants on the domain's modules, only on lines candidates cover. mutmut only
   generates; the script runs them.
4. **clean run** twice with no mutant live; flaky and source-scanning tests are dropped (kept if candidates).
5. **stage A** — each mutant vs the candidates covering **its lines**, without `-x` → K and every killer.
6. **stage B** — each mutant in K vs the kept tests covering its lines, with `-x` → L = survivors.
7. **decide** — greedy set of candidates killing all of L is kept; the rest are deletable.
8. **verify** — L vs kept + keepers must all die. Deleting is a separate, reviewed edit.

Rules, each from a failure:
| rule | failure behind it | source |
|---|---|---|
| Candidates first, kept set only on K | a third of mutants survive everything and would run every scenario | PM §3.2 |
| Per-mutant test selection by **lines**, not function | mutmut's function-level selection averaged 185 tests per mutant (median 158, max 542) | LEDGER pass 2 "Cost" |
| Only exit code 1 is a kill (stage B); a hang counts as detected; stage A credits exit 2–4 to every candidate | the safe direction both ways; mutmut "suspicious"/"segfault" re-run one at a time were real survivors or noise | `run.py` docstring; LEDGER |
| One fresh process per mutant | an in-process kill matrix hung on a futex: "A mutant can leave a thread or an event loop stuck" | PM §1.7 |
| Remove each mutant's temp dir | ~22,000 left-over pytest temp dirs filled the disk | LEDGER pass 2 "Cost" |
| Drop flaky and source-scanning tests up front | a test scanning `src/` failed on mutated source; a flaky test failed the clean run; attempts 1–4 cost ~100 + 43 min with no result | LEDGER pass 2 "Cost" |
| Cache results per mutant (diff + tests + their files) | repeats re-run only changed mutants (surface/history repeats 25 / 15 min) | `run.py`; LEDGER pass 3 "Cost" |
| Child processes must run mutated code and be covered | subprocess scenarios "run unmutated code in the child, so mutation cannot credit them"; owner kept 53 of 83 candidates for this reason | LEDGER pass 2 limit, pass 3 |
| Run in a Linux container | 17× faster (§5) | PM §1.2 |

Child-process following: mutants via inherited `MUTANT_UNDER_TEST` + `PYTHONPATH` `[bdd]`; contexts via
`scripts/prune/coverage.toml` (pytest-cov subprocess hook; coverage's own `patch=["subprocess"]` left out because
it starts a context-less tracer first) `[wt]`. `--full` mode (survivors by function = untested behaviour; owned
tests that catch nothing) `[wt]` — the committed Makefile documents `FULL=1` but does not pass it.

Cost (container, 12 workers, LEDGER pass 3): attachments 211 mutants 3 min; surface 2,036 / 38 min; history
1,217 / 66 min; jobs 1,240 / 13 min; owner 536 / 36 min. Whole tree first pass ~3–6 h projected (PM §4).

**Tools rejected:**
| tool | verdict and reason | state |
|---|---|---|
| cosmic-ray | ❌ runs the full test command per mutant; no per-mutant selection (docs read, not run) | PM §2 `[bdd]` |
| mutatest | ❌ unmaintained since 2022 | PM §2 `[bdd]` |
| pytest-testmon | ❌ for pruning: built for selection, not proof | PM §2 `[bdd]` |
| coverage-based reduction | ❌ as proof (Rothermel 1998), ✅ as filter | PM §2 |
| pytest-gremlins 1.11.3 | committed: "untested". Trial `[wt]`: ❌ `killing_test` is the literal `"unknown"` (only executor runs `-x`, reads exit code); ~1/4.5 of mutmut's mutants on the same lines | PM §2 / "Tool trial 2026-10-10" `[wt]` |
| poodle 1.3.4 | committed: "untested". Trial `[wt]`: ❌ exit code only, whole command per mutant with `-x`; a timeout counts as **not found** (wrong direction for deletion); slowest (440–578 s) | same |
| mutahunter 1.3.2 | committed: ❌ LLM non-determinism. Trial `[wt]`: repeatable at temperature 0, but crashed on 5 of 8 file runs, emitted no-op mutants, no per-test kills | same |
| LLM | ✅ only to rank candidate pairs before step 3; "It never deletes on its own say-so" | PM §3.4 |

## 7. Makefile targets in a2kay

| target | purpose | branch | script generic? |
|---|---|---|---|
| `check` | the gate; delegates to `check-container` when Docker answers, else `check-host` | `[bdd]` `[mzfh]`; on `[lin]` it runs in place | pattern generic |
| `check-host` | `guard preset lint typecheck archlint spell deps test` on the host | `[bdd]` `[mzfh]` (absent on `[lin]`) | generic |
| `check-fast` | every gate except the suite; inner loop, never Done | all | generic |
| `test` | suite on all cores, every scenario on real git, coverage floor 90 | all | app env var |
| `test-fast` | same without coverage (~50 s vs ~300 s, AGENTS §1) | all | generic |
| `test-usecases` | scenarios only, recording history, `-n 8` | all | generic |
| `test-usecases-git` | scenarios only, all on real git | all | app env var |
| `test-unit` | everything except `tests/usecases` | all | generic |
| `test-image` | build the Linux test image (shelf clone + committed `pyproject.toml` as extra contexts) | all | a2kay Dockerfile |
| `check-container` / `test-container` | gate / suite inside the image; queued through a slot on `[mzfh]` | all | generic pattern |
| `prune DOMAIN=` | mutation prune of one domain, volumes per domain and stage, report in `.prune/<d>/` | all | `run.py` a2kay-bound (§9) |
| `lineage` | act-target index + ranking into `.lineage/` (reuses prune contexts volume) | `[lin]` | a2kay-bound (§9) |
| `change-report [BASE=]` | per changed function: cc, fan-out, IO, tests; reports, exits 0 | `[lin]` | near-generic |
| `cov` | coverage report, no floor | all | generic |
| `lint` `format` `typecheck` `archlint` `spell` `deps` | ruff, pyrefly, import-linter, codespell, deptry | all | Python preset |
| `guard` `preset` | no committed local shelf source; linter preset drift | all | shelf tools |
| `eval-retrieval`, `fixture-vault`, `app` | product-specific | all | a2kay |

Not built: `make test-loop` (TASKS 2.13b), test-target `flock` (TASKS 2.14; the slot queue covers only container
jobs), wall-time/load printing on heavy targets.

## 8. Agent friction (from the handoff addendum, checked)

| friction | rule | verified? |
|---|---|---|
| Parallel agents in one worktree interleaved edits; LEDGER notes "Another session was editing other files under `tests/` in the same worktree" | one worktree + branch per agent | ✅ LEDGER pass 1 |
| One image tag for every worktree | tag per worktree / run by image ID | ✅ Makefile `TEST_IMAGE := a2kay-test`; agent report |
| CPU contention: "five jobs, load 23, gates 8×" | slot queue + print load and wall time | ⚠️ partial: 5–8× inside a full run (PREP §8), load 7–41 during prep; the five/23/8× figures are `[hand]` |
| mutmut "suspicious" false alarms "113 of 120" | exit 1 is the only kill | ⚠️ partial: LEDGER: 113 marked suspicious, 120 lost mutants re-checked, 8 tests put back |
| flaky test failed the clean run "cost 145 min" | drop flaky tests up front | ⚠️ LEDGER: attempts 1–4 ~100 + 43 min, three other causes too |
| ~22,000 temp dirs filled the disk | clean temp dirs during long runs | ✅ LEDGER |
| Hooks read the working tree, not staged content | hooks check staged content only | `[hand]` |
| Editable path sources to sibling packages blocked container build and commit guard | commit + tag package, repoint app to tag | ✅ PM §3.5 ("works only on a tree whose shelf sources are git tags"); `guard` target |
| zsh does not word-split `$VAR`; reboot wiped `/tmp` notes | arrays or `${=VAR}`; scratch in `~/.cache` | `[hand]` |
| Hermetic scrub cleared its own switch | read switches at import time | ✅ `tests/usecases/conftest.py` `_ALL_GIT` |
| pyrefly skips `.claude/` worktree paths | pass paths explicitly | ✅ TS §9 |
| Nondeterministic plugin order: 98 feature files failed collection in a fresh image | `tryfirst` | ✅ shelf commit 51fc038 (bdd-tags v0.1.1) |
| "Last call" attribution wrong 38% | check heuristic vs hand-read sample | ✅ SO §3 |
| Coverage/mutation do not follow children: "53 tests could not be judged" | follow children from day one | ⚠️ likely LEDGER pass 3: `owner` kept 53 of 83 candidates because its scenarios start the server as a child the kept set cannot credit; "could not be judged" is handoff phrasing |
| Cross-session history rewrite with pushes pending | hold pushes when told; merge before rewrite | `[hand]` |
| `uv` picked Python 3.13 in a fresh worktree, `lxml` failed | commit `.python-version` | ✅ TS §9 |
| pyrefly file-mode differs in container | run the same invocation everywhere | ✅ PREP §10b |

## 9. Promote to the shelf?

| piece | verdict | why |
|---|---|---|
| `scripts/container_slot.py` `[mzfh]` | ✅ promote now, as a host-Python tool (same shape as shelf `tools/preset_drift.py`), not a package | stdlib-only, runs before any venv; `--slots`/`--dir` already parameters; one a2kay string (default dir `~/.cache/a2kay/…`) → derive from repo name or env. **Not** into `process-lock`: e383415 rejects it ("never waits and is shared by all threads"). Stack-neutral: queues any command. |
| `scripts/lineage/metrics.py` `[lin]` | ✅ promote | pure AST, no a2kay reference; one source of cc (radon-style), fan-out, IO kinds. Python-only. |
| `scripts/lineage/check.py` `[lin]` | ✅ promote with `metrics.py` | generic except base `main` and `.lineage/index.json` path → parameters. Report-only by measurement (MC §4.1). |
| `scripts/lineage/build.py` `[lin]` | ⚠️ later | algorithm generic (act target via imports, read-back follow, baseline share 0.5) but hard-codes `LAYERS`, `ENTRYPOINTS`, `src/a2kay/`, `/app`, `/out`, and reuses the prune contexts volume. Promote together with `run.py` once both read one config. |
| `scripts/prune/run.py` `[bdd]`+`[wt]` | ⚠️ promote after parametrizing, not as-is | the method (stage A/B, line-level selection, exit-1-only, per-mutant cache, clean run) is the generic, proven part; it hard-codes `src/a2kay/` (`module_globs`, `domain_of_file`), `--cov=a2kay`, `/app /state /out`; the `--full` mode and child-process coverage are uncommitted. Pytest + mutmut + coverage.py only. |
| `scripts/prune/domains.toml` | ❌ stays (schema goes with `run.py`) | a2kay's module map |
| `scripts/prune/test.Dockerfile` | ❌ stays; a template for the skill | torch CPU, llama.cpp, three build contexts — all a2kay |
| `RecordingHistory`, rigs, clock offset | ❌ | a2kay types (PREP §12c) |
| `mcp-steps`, `json-match`, `bdd-tags`, `*.testing` doubles | already shelved | ADR 0044 amendment 2026-10-10; Gherkin only where steps are shared — a pilot rewriting two packages' own tests as features grew them 50–90% in lines |
