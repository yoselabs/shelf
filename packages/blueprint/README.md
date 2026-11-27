# blueprint

**Stop judging a repository's setup by reading it.** The check engine behind the shelf's
`/blueprint` skill: it detects what the repo is, runs every checkpoint that applies, in one
process, and reports per checkpoint whether it is set up, whether it works, the evidence, and
the remediation with who applies it (auto, agent, owner). Stdlib only.

## Run it

Release recipes (`check-all`) are opt-in: set `[tool.blueprint.gate] release-gate = true` in `pyproject.toml`, then re-render.

`blueprint init` sets a repo up; `blueprint check` judges it; `blueprint gate <step>` runs one step of `just check` (the justfile and hooks call those). From any repo, with a shelf clone beside it — no install:

```bash
PYTHONPATH=../shelf/packages/blueprint/src python3 -m blueprint check --repo .
```

| flag | effect |
|---|---|
| `--brief` | one line per checkpoint that is not passing; what `just blueprint` prints |
| `--list [PREFIX]` | list the checkpoints instead (id, statement, the fact that turns each on), with `--json` as JSON |
| `--json` | the run as JSON, for agents and evals |
| `--write` | `.blueprint/reports/README.md` (one row per concern, grouped by layer) and `<concern>.md`, one table per concern: a git-ignored folder; the tracked output is the audit record `docs/blueprint/checkpoints.txt` |
| `--audit` | also the audit-only checkpoints: slow ones (a fresh clone running `just check`) and ones that read this machine's bd database, which a bare clone does not have |
| `--concern X` | one concern only |

Exit codes: `0` everything passes or does not apply · `1` something fails or is not set up ·
`2` nothing fails but something could not be checked — never a pass.

Processes default to a 120-second timeout. Set `BLUEPRINT_TIMEOUT` to a number of seconds (a float) to raise the timeout on loaded machines. Each call uses the greater of its own timeout and this environment value; the variable never lowers a call's timeout. Git timeouts are reported with the command and elapsed timeout.

## Verdicts

`not set up` · `failing` · `passing` · `not applicable` · `not checked`, from two answers per
checkpoint: *set up?* and *working?* A check that crashes, or passes with no evidence, is
`not checked`.

## Test units: a repo that is not a uv workspace (`pyproject.toml`)

A workspace is planned per `packages/*`. Any other repo declares units, so `just test` reruns only what a change reaches:

```toml
[tool.blueprint.test]
coverage = "coverage"      # or "pytest-cov"; absent: no coverage, no floor
floor = 90                 # whole-repo percent, over every unit's data (cached ones too)
pytest-args = ["-n", "auto", "--dist", "loadgroup", "-q"]
marks = "not slow"         # pytest's -m expression
env = { COVERAGE_CORE = "sysmon" }

[tool.blueprint.test.units.ui]
paths = ["tests/ui"]
reads = ["src/app/ui/*.js"]   # files tests read that no import names (JS run under node, fixtures)
```

`pytest-args` and `marks` apply to every pytest run, before the CLI's `--pytest-args`.
`env` adds string values to the test processes' inherited environment; the coverage runner's
`COVERAGE_FILE` takes precedence. Invalid types for these keys are ignored. Changing any of
the three settings changes every unit's key. `gate test-all` honors them too, keeping its
default `-n auto` unless `pytest-args` contains `-n`.

The key of a unit hashes its files, every first-party module they import (found by reading the imports), the `conftest.py` above them, the `reads` files,
`uv.lock` and the dependency and pytest/coverage parts of `pyproject.toml`. An import it cannot see (`importlib` with a computed name) goes in `reads`.
Do not define your own `test` recipe: `gate.recipe-shadowing` fails it unless an `[[override]]` says why (ADR 0033).

`blueprint gate test-all` runs every test with a coverage floor: `[tool.blueprint.test] floor` takes precedence over
`[tool.coverage.report] fail_under`, with 65 as the fallback. The resolved floor is passed explicitly to pytest-cov.

`fail_under` in `[tool.coverage.report]` is the whole repo's floor: with units, each unit runs under `--cov-fail-under=0` and the
combined data is judged once. A package that tests run against its installed wheel measures 0% unless `[tool.coverage.run]`
sets `source_pkgs = ["<package>"]` and `[tool.coverage.paths]` maps the installed path back to `src/`.

## Run the pinned engine

A recipe calls `uv run blueprint ...` (blueprint is a dev dependency, pinned by the lock), never `PYTHONPATH=<shelf clone>` or `--reference <shelf file>`: a clone
moves with whatever any session has checked out there. `gate.recipe-calls` fails a recipe that does, and one that passes a flag blueprint does not have.

## State: `docs/blueprint/blueprint.toml`

```toml
[profile]                 # overrides what detection finds
kind = "application"      # application | library | infrastructure
surfaces = ["cli"]
traits = ["stores-data"]

# The classification (ADR 0026): what the agent or owner judged about the report's "Facts and evidence".
# A declaration only adds. Claims come from the closed lists: kinds library | application | infrastructure;
# surfaces http-server | mcp-server | cli | web-ui | desktop-app | game; traits deployed | ships-image |
# holds-secrets | stores-data | llm-backed | scheduled-jobs. A claim off the lists, or a blank reason, is a state problem.
[[profile.classified]]    # accept a claim: it joins the profile (surfaces, traits, or the kind)
claim = "mcp-server"
decided_by = "agent"      # detected | agent | owner (default agent)
reason = "a FastMCP server; MCP is its main surface"

[[profile.rejected]]      # silence evidence; never removes a fact
claim = "mcp-server"
where = "packages/mcp-bridge/pyproject.toml:11"   # the evidence it rejects; matched by claim and file, so a move to another file is reported again
decided_by = "agent"
reason = "a client library, not a server"

[profile.frameworks]      # overrides detection: framework -> its folder
godot = "src/Game.Godot"

[settings]
clean-clone-seconds = 120 # gate.clean-clone's budget

# Every exception to a checkpoint is one [[override]] (ADR 0026); nothing else excuses a row.
[[override]]              # counts as passing while it is justified
id = "gate.hooks-recipe"   # a checkpoint id (`blueprint check --list`)
reason = "the owner installs hooks by hand on each machine"
decided_by = "owner"      # owner | agent; missing reads "unknown" in the report
adr = "0003"              # cites the decision record that makes the exception durable (not read by blueprint); no expiry needed
# expires = 2027-04-01    # a temporary exception instead of adr
# code = "not-applicable" # optional, legacy: test-data | remediated | not-applicable | not-supported | not-detected

[[override]]              # with a scope the check still runs; only the offenders the scope names are dropped
id = "stack.python-uv.tests"
scope = "tools/legacy_tests"   # a path glob, "path:line", or "service:<compose service>"
reason = "vendored suite, run by its owner"
expires = 2027-04-01

[[override]]              # a throwaway or vendored path: stack detection and role globs skip it
id = "detection"
scope = "prototype"
reason = "throwaway spikes bind nothing"
expires = 2027-04-01
```

Excusing a file or folder from detection (`id = "detection"`) is also how to except a whole stack for it: a script kept out of detection is judged by no `stack.shell.*` row.

Replaced shapes: `[[profile.ignore]]` still works and is reported with the `[[override]]` to write instead;
`# strict: no -e` (shell strict mode) and the compose policy's `x-policy-exempt` still
work for now, each reported (a notice, a conftest warning) with the override to paste; they will stop being honoured. The compose policy reads this same file:
`conftest test --combine --policy policy docs/blueprint/blueprint.toml <compose files>` with ids `compose.<rule>`
(`privileged`, `host_network`, `docker_socket`, `unbound_port`, `default_network`, `healthcheck`) and
`scope = "service:<name>"`. A scoped override is only read by a check that asks for it (`Context.excused`).
Every report starts, after its header, with the list of all overrides (id, scope, reason, decided by, expiry or ADR).

**Every exception is justified** ([ADR 0022](../../docs/adr/0022-every-exception-is-justified.md)): a non-empty
`reason`, and either `expires` or `adr`. An `adr` cites the decision record (blueprint does not read it); an exception with neither field is a problem the gate reports (exit 1), and it counts for nothing.

A written report's header names the shelf commit and package version that produced it, the checkpoint-set hash,
and the scope: concerns checked, concerns not run, and whether the audit-only checkpoints ran.

## Concerns in v0.1

| layer | concern | checkpoints |
|---|---|---|
| generic | gate | `one-command` · `runner` (a Makefile-only gate fails: the runner is just, ADR 0023; the graph is read from `just --dump --dump-format json`; a Makefile is not read) · `runs-blueprint` · `no-ci` (no repository has GitHub Actions configuration, ADR 0027) · `hooks-recipe` · `hooks-installed` (audit only) · `guards-have-red-tests` (follows `just check` into pre-commit hooks) · `checkers-wired` · `lfs-binaries` (a repo with LFS patterns: every binary blob is a pointer, read from the blob since `--eol` cannot judge a `-text` file) · `lfs-installed` (audit only: git-lfs and its filter in this clone) · `default-branch` (audit only) · `git-remote` (audit only) · `clean-clone` (audit only) |
| generic | backlog | `tracker` · `strict-config` (audit only) · `no-tracked-export` · `no-local-override` · `lint` (audit only) · `no-tracker-file` |
| stack | stack/`<stack>` | `profile`, then one row per role: `toolchain` · `formatter` · `linter` · `types` · `dependencies` · `tests` · `coverage` · `spelling` · `architecture`, judged from `profiles/<stack>.toml` (python-uv evidenced, dotnet provisional; the toolchain row also checks every dotnet install against global.json); `python-uv.uv-tool` (audit only): an application's installed uv tool matches uv.lock; `tool-pins`: every tool the repo runs (uv, just, prek, bd, git-lfs, godot) is pinned exactly in mise.toml, locked in mise.lock and installed by a `mise install --locked` recipe, with no second pin beside .python-version, global.json or rust-just (ADR 0024); `agent-cli-pins`: mise.toml pins no self-updating agent CLI (codex, claude code, opencode, gemini; the list is `tools.toml`), and a machine-owned tool such as git takes a floor (`>=`) instead of a pin; `tools-installed` (audit only): each pinned tool on PATH is its pinned version |
| framework | framework/`<name>` | `profile`, then one row per role its profile names (godot, unity, mcp, provisional: framework-version · project-hygiene · binary-assets · build · tests · surface-integrity · architecture · hooks; `embedded-script-lint` projects no row); paths may use `{root}` (the project folder) and globs |
| agent | agents | `instructions` · `bd-metrics-off` · `session-hooks` · `worktrees` |

With `--audit`, a gate row that is failing or not set up (`one-command`, `runner`, `hooks-recipe`, `runs-blueprint`, `clean-clone`) also names any remote-tracking branch (`origin/*`, local refs, no fetch) ahead of the default branch that changes a gate file (justfile, Makefile, hook config), and hands the fix to the owner: merge that branch or remediate on main, not a parallel gate. The branch itself is never checked.

Hooks follow one recipe: prek owns them through `.pre-commit-config.yaml` and bd's five events run
from it (`blueprint init` writes it, and runs `prek install` unless `--no-hooks`); bd never installs hooks itself. A framework's or stack's own gate script is a recipe too (unity-integrity, dockerfile-pins, compose-policy, godot, dotnet-coverage): `blueprint init` writes it into `tools/` (a rego policy into `policy/`) when the stack is detected, and the repo owns the copy.

A stack with no profile, or a role its profile leaves untested, is a **blueprint gap**: reported
every run, never a pass, but left out of the exit code, since the shelf lacks the answer, not the repo.
A new stack is a new `profiles/<stack>.toml`, not code.

## Knowledge and agent docs

Blueprint checks and seeds none of it: decision records, the glossary and `docs/agents/` live in `any-knowledge` (`python -m any_knowledge index|check|seed`), which a repo wires into its own `check-extra`. An override may still cite a decision record with `adr = "NNNN"`; blueprint does not read it.

## Survey

The run survey is data, `survey.toml` (experience, completeness, correctness, cost; closed answers); the skill
fills it into `docs/blueprint/survey.md` after every run. There is no verb for it.

A new checkpoint is one decorated function in the module of the plugin that owns it, `blueprint/concerns/<plugin>/<module>.py`
(each plugin is a manifest, `blueprint/plugins/<id>.toml`, listing its rows and modules; a repo switches one off in
`[plugins]` of `docs/blueprint/blueprint.toml`), returning a `Finding`, with a passing test and a planted-violation test (`blueprint.testing.Repo`).
