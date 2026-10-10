---
name: blueprint
description: The shelf's standard for every software repository — start a new repo, or audit an existing one, against it. Runs the blueprint check engine over the repo, writes a summary and a verdict table per concern to docs/blueprint/, proposes a remediation per finding (auto, agent or owner), and applies them only after the owner's yes. Invoke as /blueprint in the repository to judge.
disable-model-invocation: true
---

# blueprint

You are the manager of this repo's setup, not a narrator of it. The engine judges; you decide
what to fix, delegate the fixing, and bring the owner only what is theirs to decide.

**Resume rule:** after compaction or a new session, re-invoke the skill, read
`docs/blueprint/README.md` in the repo, and continue from the first concern that is not all ✅.

**Verdicts** come from the engine, never from your judgment: `not set up` · `failing` ·
`passing` · `not applicable` · `not checked`. `not checked` is never a pass.

**Layers.** Every concern belongs to one, and every report and message keeps them apart:

| layer | what it judges | concerns in v0.1 |
|---|---|---|
| Generic | any repo, any language | `gate` (one command, CI, hooks, guards, clean clone), `backlog` (beads) |
| Stack-specific | one language's tools, from the shelf's profile for it | `stack/<stack>`: toolchain, formatter, linter, types, dependencies, tests, coverage, spelling, architecture |
| Framework-specific | an engine or framework on top of a stack, from its profile | `framework/<name>` (godot: engine version, project hygiene, headless build, tests, scene integrity, architecture, CI) |
| Agent harness | what agents run inside | `agents`: AGENTS.md, session env, session hooks |

A stack or framework with no profile, or a role its profile leaves open, is a **blueprint gap**: "no standard
for this stack yet". It is the shelf's gap, not the repo's; say it in those words.

**Directions:** audit (default; changes only `docs/blueprint/`) · remediate (after the owner's
yes) · start (empty repo: audit, then remediate) · reabsorb (gaps go to the shelf as beads).

## 1. Find the engine

`packages/blueprint/src` in the shelf; use the first that exists: `$SHELF_HOME/…`,
`../shelf/…`, `~/Workspaces/shelf/…` (or, under Claude Code, `${CLAUDE_SKILL_DIR}/../../…`).
For a clone, `git -C <shelf> pull --ff-only` first; on failure say so in one line and go on.
Everything below runs as `PYTHONPATH=<engine> python3 -m blueprint …`: Python 3.11+, nothing to
install, any agent harness.

## 2. Audit

1. `check --repo . --audit --write` writes `docs/blueprint/README.md` (one row per concern,
   grouped by layer) and one table per concern. Read the README and `--summary` only; open a
   concern's file only to remediate it. The JSON (`--json`) is for scripts, not for reading.
2. A `not checked` row that is not a blueprint gap: find why (a missing tool, no commits).
3. Show the owner the plan (§4) and stop.

## 3. Remediate (after the owner's yes)

The owner's one yes covers the whole plan. Per concern, in layer order (generic, stack, agent):

- `auto` rows: run the engine's remediation as written.
- `agent` rows: do them, or delegate (§5) when a concern has several.
- `owner` rows: one batched question round, your default worded so "yes" accepts it.
- Re-run `check --concern <c> --audit`; a fix never seen ✅ is unverified, and you say so.
- A row right to leave failing becomes an override in `docs/blueprint/blueprint.toml` (code,
  reason, expiry) only with the owner's yes. Rows still not ✅ at the end become beads.
- Finish with the repo's own `make check` green and `--write` again.

## 4. What the owner sees

The owner sees outcomes and decisions, never the process: no tool-by-tool narration, no recap of
the report files, no step lists. In chat, only:

1. **The summary**: `check --summary` as printed, one row per concern under its layer.
2. **Need from you**: decisions that are the owner's, at most three, each with your default.
3. Mistakes that reached the owner, if any. One line each.

Everything else lives in `docs/blueprint/`. Marks carry meaning only: ✅ passing · ❌ failing ·
⚠️ needs the owner · 🔒 not checked. Opener ≤10 words. A label the owner has not used gets a
one-clause gloss by its job. A large or structural change (layers, a folder layout, the test tree)
gets a short plain-words picture first; much work ahead gets one page outlining it.

## 5. Spend tokens like a manager

- The engine is free: it reads files and runs tools without loading them into context. Never
  re-inspect by hand what a checkpoint already judged.
- Delegate bulk work to a cheaper model when the harness allows it (Claude Code: the Agent tool
  with `model: sonnet`; opencode: a subagent with a smaller model): one worker per concern to
  remediate, one to research a missing stack or framework profile, one to fill the survey. Give each worker the
  concern's report file and the remediation rows; take back only "done / not done + why".
  Without subagents, do the same work inline, one concern at a time.
- Keep your own context to the README, the plan and the decisions.

## 6. Start, reabsorb

- **Start:** audit the empty repo, then on the yes: tracker (`bd init --skip-hooks`, strict
  settings) → hooks (`recipe hooks > .pre-commit-config.yaml`, `prek install`) → gate (`make check`,
  CI) → the stack's profile → the framework's profile → agent harness. A Python repo: the shelf onboarding writes most of the
  gate (`python3 <shelf>/.agents/skills/onboard-consumer/scripts/onboard.py --repo .`).
- **Reabsorb:** a blueprint gap, or anything the run met that no checkpoint covers, becomes one
  bead in the **shelf** titled `blueprint lacks: <what>` (repo, evidence, the checkpoint or profile
  you would add). Never add it inside the consumer.

## 7. Survey (end of every run)

`survey --repo . > docs/blueprint/survey.md`, answer every row from the closed set with one line of
evidence, then `survey --check docs/blueprint/survey.md` must print `complete`. Tell the owner the
path in one line, to relay to the shelf. Answer as a critic of the run: a "yes" without evidence is
a "partly".

## Gotchas

- Writing ✅ for a row the engine reported otherwise is the failure this skill exists to prevent.
- Hooks: never let bd install its own (`bd init --skip-hooks`; `bd hooks install` never). bd's
  hooks run from `.pre-commit-config.yaml` via prek; bd's own injection makes a failing check stop
  blocking commits in other managers' hook files.
- `--audit` adds the audit-only rows: slow ones (a fresh clone running `make check`) and ones
  reading this clone's state (installed hooks, bd's database). The repo's `make blueprint` skips them.
- v0.1: concerns `gate`, `backlog`, `stack`, `framework`, `agents`; profiles python-uv
  (evidenced), dotnet and godot (provisional). Do not invent rows for what the engine does not check.
- Two projects of one framework (a game and a prototype spike) each get a table; the owner names
  the real one in `docs/blueprint/blueprint.toml` (`[profile.frameworks] godot = "src/Game.Godot"`).
