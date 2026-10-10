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
| `--summary` | one row per concern, grouped by layer (generic, stack-specific, agent harness) |
| `--gate` | one line per checkpoint that is not passing; what `make blueprint` prints |
| `--json` | the run as JSON, for agents and evals |
| `--write` | `docs/blueprint/README.md` (the summary) and `<concern>.md`, one table per concern |
| `--audit` | also the audit-only checkpoints: slow ones (a fresh clone running `make check`) and ones that read this machine's bd database, which CI and the gate container do not have |
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

[settings]
clean-clone-seconds = 120 # gate.clean-clone's budget

[[override]]              # counts as passing until it expires
id = "gate.ci"
code = "not-applicable"   # test-data | remediated | not-applicable | not-supported | not-detected
reason = "a local-only tool, never pushed"
expires = 2027-04-01
```

## Concerns in v0.1

| layer | concern | checkpoints |
|---|---|---|
| generic | gate | `one-command` · `ci` · `hooks-recipe` · `hooks-installed` (audit only) · `guards-have-red-tests` · `clean-clone` (audit only) |
| generic | backlog | `tracker` · `strict-config` (audit only) · `no-tracked-export` · `no-local-override` · `lint` (audit only) · `no-tracker-file` |
| stack | stack/`<stack>` | `profile`, then one row per role: `toolchain` · `formatter` · `linter` · `types` · `dependencies` · `tests` · `coverage` · `spelling` · `architecture`, judged from `profiles/<stack>.toml` (python-uv evidenced, dotnet provisional) |
| framework | framework/`<name>` | `profile`, then one row per role its profile names (godot, provisional: engine-version · project-hygiene · scripts-lint · headless-build · tests · scene-integrity · architecture · ci); paths may use `{root}` (the project folder) and globs |
| agent | agents | `instructions` · `bd-metrics-off` · `session-hooks` |

Hooks follow one recipe: prek owns them through `.pre-commit-config.yaml` and bd's five events run
from it (`blueprint recipe hooks` prints it); bd never installs hooks itself.

A stack with no profile, or a role its profile leaves untested, is a **blueprint gap**: reported
every run, never a pass, but left out of the exit code, since the shelf lacks the answer, not the repo.
A new stack is a new `profiles/<stack>.toml`, not code.

## Survey

`blueprint survey` prints the run survey (`survey.toml`: experience, completeness, correctness,
cost; closed answers); the skill fills it into `docs/blueprint/survey.md` after every run, and
`blueprint survey --check FILE` fails until every question is answered.

A new checkpoint is one decorated function in `blueprint/concerns/<concern>.py` returning a
`Finding`, with a passing test and a planted-violation test (`blueprint.testing.Repo`).
