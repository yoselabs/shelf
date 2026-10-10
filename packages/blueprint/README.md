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
| `--gate` | one line per checkpoint that is not passing; what `make blueprint` prints |
| `--json` | the run as JSON, for agents and evals |
| `--write` | `docs/blueprint/<concern>.md`, one table per concern |
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

[settings]
clean-clone-seconds = 120 # gate.clean-clone's budget

[[override]]              # counts as passing until it expires
id = "gate.ci"
code = "not-applicable"   # test-data | remediated | not-applicable | not-supported | not-detected
reason = "a local-only tool, never pushed"
expires = 2027-04-01
```

## Concerns in v0.1

| concern | checkpoints |
|---|---|
| gate | `one-command` · `ci` · `one-hook-manager` (audit only) · `guards-have-red-tests` · `clean-clone` (audit only) |
| backlog | `tracker` · `strict-config` (audit only) · `metrics-off` · `no-tracked-export` · `no-local-override` · `lint` (audit only) · `no-tracker-file` |

A new checkpoint is one decorated function in `blueprint/concerns/<concern>.py` returning a
`Finding`, with a passing test and a planted-violation test (`blueprint.testing.Repo`).
