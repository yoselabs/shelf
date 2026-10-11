# blueprint

**Stop judging a repository's setup by reading it.** The check engine behind the shelf's
`/blueprint` skill: it detects what the repo is, runs every checkpoint that applies, in one
process, and reports per checkpoint whether it is set up, whether it works, the evidence, and
the remediation with who applies it (auto, agent, owner). Stdlib only.

## Run it

From any repo, with a shelf clone beside it — no install:

```bash
PYTHONPATH=../shelf/packages/blueprint/src python3 -m blueprint check --repo .
```

| flag | effect |
|---|---|
| `--summary` | one row per concern, grouped by layer (generic, stack-specific, agent harness); says how many audit-only checkpoints it left out, so pair it with `--audit` to match a README written by `--audit --write` |
| `--gate` | one line per checkpoint that is not passing; what `just blueprint` prints |
| `--json` | the run as JSON, for agents and evals |
| `--write` | `docs/blueprint/README.md` (the summary) and `<concern>.md`, one table per concern |
| `--audit` | also the audit-only checkpoints: slow ones (a fresh clone running `just check`) and ones that read this machine's bd database, which CI and the gate container do not have |
| `--concern X` | one concern only |

Exit codes: `0` everything passes or does not apply · `1` something fails or is not set up ·
`2` nothing fails but something could not be checked — never a pass.

## Verdicts

`not set up` · `failing` · `passing` · `not applicable` · `not checked`, from two answers per
checkpoint: *set up?* and *working?* A check that crashes, or passes with no evidence, is
`not checked`.

## State: `docs/blueprint/blueprint.toml`

```toml
[profile]                 # overrides what detection finds
kind = "application"      # application | library | infrastructure
surfaces = ["cli"]
traits = ["stores-data"]

[profile.frameworks]      # overrides detection: framework -> its folder
godot = "src/Game.Godot"

[[profile.ignore]]        # a throwaway or vendored path: stack detection and role globs skip it
path = "prototype"
reason = "throwaway spikes bind nothing"
expires = 2027-04-01      # or adr = "NNNN"

[settings]
clean-clone-seconds = 120 # gate.clean-clone's budget

[[override]]              # counts as passing while it is justified
id = "gate.ci"
code = "not-applicable"   # test-data | remediated | not-applicable | not-supported | not-detected
reason = "builds and the gate run on the owner's machines"
adr = "0003"              # an accepted ADR in docs/adr/ records the durable decision; no expiry needed
# expires = 2027-04-01    # a temporary exception instead of adr
```

**Every exception is justified** ([ADR 0022](../../docs/adr/0022-every-exception-is-justified.md)): a non-empty
`reason`, and either `expires` or `adr`. An `adr` must name an accepted ADR in `docs/adr/`; one that is missing,
not accepted, or an exception with neither field is a problem the gate reports (exit 1), and it counts for nothing.

A written report's header names the shelf commit and package version that produced it, the checkpoint-set hash,
and the scope: concerns checked, concerns not run, and whether the audit-only checkpoints ran.

## Concerns in v0.1

| layer | concern | checkpoints |
|---|---|---|
| generic | gate | `one-command` · `runner` (a Makefile-only gate fails: the runner is just, ADR 0023; the graph is read from `just --dump --dump-format json`, a Makefile still being judged) · `runs-blueprint` · `ci` · `ci-no-manifest-edit` · `hooks-recipe` · `hooks-installed` (audit only) · `guards-have-red-tests` (follows `just check` into pre-commit hooks) · `checkers-wired` · `default-branch` (audit only) · `git-remote` (audit only) · `clean-clone` (audit only) |
| generic | backlog | `tracker` · `strict-config` (audit only) · `no-tracked-export` · `no-local-override` · `lint` (audit only) · `no-tracker-file` |
| stack | stack/`<stack>` | `profile`, then one row per role: `toolchain` · `formatter` · `linter` · `types` · `dependencies` · `tests` · `coverage` · `spelling` · `architecture`, judged from `profiles/<stack>.toml` (python-uv evidenced, dotnet provisional; the toolchain row also checks every dotnet install against global.json); `python-uv.uv-tool` (audit only): an application's installed uv tool matches uv.lock |
| framework | framework/`<name>` | `profile`, then one row per role its profile names (godot, unity, mcp, provisional: framework-version · project-hygiene · binary-assets · embedded-script-lint · build · tests · surface-integrity · architecture · ci · hooks · agent-guidance); paths may use `{root}` (the project folder) and globs |
| agent | agents | `instructions` · `bd-metrics-off` · `session-hooks` · `worktrees` · `culture-files` (placeholders in docs/agents/, AGENTS.md and CLAUDE.md) · `managed-block` |

Hooks follow one recipe: prek owns them through `.pre-commit-config.yaml` and bd's five events run
from it (`blueprint recipe hooks` prints it); bd never installs hooks itself. A framework's own gate script is a recipe too (`blueprint recipe unity-integrity`): the repo copies it into `tools/` and owns the copy.

A stack with no profile, or a role its profile leaves untested, is a **blueprint gap**: reported
every run, never a pass, but left out of the exit code, since the shelf lacks the answer, not the repo.
A new stack is a new `profiles/<stack>.toml`, not code.

## Culture templates

`blueprint template --repo .` copies the `docs/agents/` files the profile requires (`templates/`)
and writes the AGENTS.md managed block; it never overwrites a file the repo has.

## Survey

`blueprint survey` prints the run survey (`survey.toml`: experience, completeness, correctness,
cost; closed answers); the skill fills it into `docs/blueprint/survey.md` after every run, and
`blueprint survey --check FILE` fails until every question is answered.

A new checkpoint is one decorated function in `blueprint/concerns/<concern>.py` returning a
`Finding`, with a passing test and a planted-violation test (`blueprint.testing.Repo`).
