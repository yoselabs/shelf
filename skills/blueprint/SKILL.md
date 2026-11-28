---
name: blueprint
description: The shelf's standard for every software repository — start a new repo, or audit an existing one, against it. Runs the blueprint check engine over the repo, writes a summary and a verdict table per concern to docs/blueprint/, proposes a remediation per finding (auto, agent or owner), and applies them only after the owner's yes. Invoke as /blueprint in the repository to judge.
disable-model-invocation: true
---

# blueprint

You are the manager of this repo's setup, not a narrator of it. The engine judges; you decide
what to fix, delegate the fixing, and bring the owner only what is theirs to decide.

**Strict and pushy.** The standard is the point: never soften a verdict, never offer to skip a row,
never call a gap "fine for now". Each finding says what is wrong, why it matters (the checkpoint's
statement, one line) and the fix. No prose beyond that. The why behind every standard is one line in the shelf's
`docs/adr/INDEX.md` (its ADR holds the reasons); cite the ADR number when challenged.

**Not a chat.** The owner may ask or challenge anything: answer in at most five lines, with
evidence, then return to where the run was and show the pending decision again. A challenge that
holds becomes a `blueprint lacks:` bead (§6), not an exception granted in chat.

**Resume rule:** after compaction or a new session, re-invoke the skill, read
`.blueprint/reports/README.md` in the repo (re-run `check --audit --write` if it is missing: the folder is git-ignored), and continue from the first concern that is not all ✅.

**Verdicts** come from the engine, never from your judgment: `not set up` · `failing` ·
`passing` · `not applicable` · `not checked`. `not checked` is never a pass.

**Layers.** Every concern belongs to one, and every report and message keeps them apart:

| layer | what it judges | concerns in v0.1 |
|---|---|---|
| Generic | any repo, any language | `gate` (one command, no CI, hooks, guards, clean clone), `backlog` (beads), `secrets` (sops files sealed and covered by a rule) |
| Stack-specific | one language's tools, from the shelf's profile for it | `stack/<stack>`: toolchain, formatter, linter, types, dependencies, tests, coverage, spelling, architecture; python-uv also the Python and uv pins (images included), shell also strict mode |
| Framework-specific | an engine or framework on top of a stack, from its profile | `framework/<name>` (godot, unity, mcp): framework version, project hygiene, build, tests, surface integrity, architecture |
| Agent harness | what agents run inside | `agents`: AGENTS.md, session env, session hooks |

A stack or framework with no profile, or a role its profile leaves open, is a **blueprint gap**: "no standard
for this stack yet". It is the shelf's gap, not the repo's; say it in those words, and push to close
it (§6): every gap is one of the owner's decisions, defaulted to "research it now".

**Directions:** audit (default; changes only `docs/blueprint/`) · remediate (after the owner's
yes) · start (empty repo: audit, then remediate) · reabsorb (gaps go to the shelf as beads).

## 1. Find the engine

A repo the shelf onboarded has `blueprint` as a dev dependency pinned by git tag: run `uv run blueprint …`, no clone needed. Otherwise
use `packages/blueprint/src` in the shelf, the first that exists: `$SHELF_HOME/…`, `../shelf/…`, `~/Workspaces/shelf/…` (or, under Claude
Code, `${CLAUDE_SKILL_DIR}/../../…`) and run `PYTHONPATH=<engine> python3 -m blueprint …` (Python 3.11+, nothing to install). For a clone,
`git -C <shelf> pull --ff-only` first; on failure say so in one line and go on.

`blueprint init` sets a repo up (detect the stack, audit, plan, write only what is missing; `--no-hooks` leaves the git hooks alone) and ends with
the rows it could not set up. `blueprint gate <step>` runs one step of `just check` (the justfile and hooks call them; you rarely type one):
`guard` (no committed local shelf source), `preset` (linter config against the shelf's snapshot), `render` (`--check` fails when the
blueprint-owned parts of the justfile differ from what the repo's stacks render), `test` (the repo's tests through any-gate: receipts skip
what passed, a lease queues runs); `check --brief` is the per-commit step. A repo's justfile imports the rendered base; it does not copy recipes.

## 2. Audit

1. `check --repo . --audit --write` writes `.blueprint/reports/README.md` (git-ignored; one row per concern,
   grouped by layer) and one table per concern. Read the README and `--audit` only; open a
   concern's file only to remediate it. The JSON (`--json`) is for scripts, not for reading.
2. A `not checked` row that is not a blueprint gap: find why (a missing tool, no commits).
3. Read the report's "Facts and evidence" (also `facts_and_evidence` in the JSON); each item is accepted, rejected or
   awaiting judgement, and the "To classify" list holds the awaiting ones (they do not fail the gate; resolve
   them). Write each judgement in `docs/blueprint/blueprint.toml`: `[[profile.classified]]` (`claim`, `decided_by`,
   `reason`) accepts a fact or evidence; `[[profile.rejected]]` (`claim`, `where` = the evidence's `path:line`,
   `decided_by`, `reason`) silences evidence and never removes a fact. Claims come from the closed lists; `decided_by`
   is `agent`, or `owner` with the reason in the owner's words. Accept facts and high-confidence evidence; judge
   low-confidence evidence yourself, or ask the owner when unsure; ask the owner what nothing detects (a game, a
   desktop app, library versus application). One numbered question round, grouped, each with your recommended answer.
4. Show the owner the plan (§4) and stop.

The layout row `layout.stacks-in-own-folders` (ADR 0034) fails a repo with two code bases where one sits at the root or in a folder not
named `backend/` or `frontend/`. Its remediation names the `git mv`; the move is the owner's (it touches every path a recipe, hook and
Dockerfile names), so show the list of broken paths with the plan, run `blueprint gate render` after the move, and never weaken the row.
One code base at the root, with a node folder that only runs build tools, passes.

The audit writes nothing tracked (ADR 0018). The pinned tag decides which checkpoints judge the repo, so a
checkpoint the shelf added fails right after a pin bump. A repo that cannot fix one yet waives it in its config:
`[[tool.blueprint.waivers]]` with `id`, `reason`, `until` (at most 90 days out). An expired, reasonless or
unknown-id waiver fails. A leftover `docs/blueprint/checkpoints.txt` or tracked report fails `gate.no-audit-leftovers`.

## 3. Remediate (after the owner's yes)

The owner's one yes covers the `auto` and `agent` rows, never the `owner` rows. Per concern, in layer order (generic, stack, agent):

- `auto` rows: run the engine's remediation as written.
- `agent` rows: do them, or delegate (§5) when a concern has several.
- `owner` rows: one decision per row, asked for that row by name (a round may group them for reading,
  but a blanket yes never applies an owner row); an `unproven-standard:` row is a provisional
  profile's recipe, which applied wholesale broke lifesim clones (shelf-o5a) and packages
  (shelf-ir7), so show its evidence with the question. Your default worded so "yes" accepts it.
- Re-run `check --concern <c> --audit`; a fix never seen ✅ is unverified, and you say so.
- A row right to leave failing becomes an override in `docs/blueprint/blueprint.toml` only with the
  owner's yes. Every exception is justified: a reason, and either `expires` (temporary) or
  `adr = "NNNN"` naming the accepted ADR that records the durable decision (the owner installs hooks by hand
  on each machine). **Every exception is this one `[[override]]` table**: `id` (a checkpoint id), optional `scope`
  (a path glob, `path:line`, or `service:<compose service>`: the check still runs and drops only what the scope
  names), `reason`, `decided_by` (`owner` or `agent`), and `expires` or `adr`. A path detection must skip (a
  throwaway spike) is the same table with `id = "detection"` and `scope` = the path (the old `[[profile.ignore]]`,
  `# lenient:`, `# strict: no -e` and `x-policy-exempt` are the old shapes: still honoured for now, but the report prints a notice with the override to
  write in their place). Excusing a file from detection is also how to except a whole stack for it. A linter's own suppression (`# noqa`, hadolint `ignored:`, `# shellcheck disable`) stays
  where the linter reads it. Every report lists all overrides first. Rows still not ✅ at the end become beads.
- `blueprint check --list [id-prefix] [--json]` lists every checkpoint id, its statement and the fact that turns it on: read it before writing an override or declaring a missed fact.
- Finish with the repo's own `just check` green and `--write` again. Never run `just check-all` for this: `check` already runs what the change
  reaches and skips what passed on the same input; `check-all` (every test, the coverage floor) is the release gate, before a tag.

## 4. What the owner sees

The owner sees outcomes and decisions, never the process: no tool-by-tool narration, no recap of
the report files, no step lists. In chat, only:

1. **The summary**: `check --audit` as printed (without `--audit` it leaves out the audit-only rows and
   shows fewer failures than the README), one row per concern under its layer.
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

- **Start:** audit the empty repo, then on the yes: `blueprint init` (the gate as rendered justfile parts with `just blueprint` in it, the preset tables,
  prek hooks from the recipe unless `--no-hooks`, the stack's recipe files; the runner is `just`, pinned as
  `rust-just`; beads setup is the owner's), then fill every `{{name}}` from the repo → the stack's profile → the
  framework's profile. Never add CI: no repository has GitHub Actions (ADR 0027).
- **Reabsorb:** a blueprint gap, or anything the run met that no checkpoint covers, becomes one
  bead in the **shelf** titled `blueprint lacks: <what>` (repo, evidence, the checkpoint or profile
  you would add). Never change blueprint from inside the consumer.
- **Grow a profile from here:** for a stack, framework or role with no standard, propose research
  as a decision (default yes). On the yes, one worker researches it against this repo (strictest
  maintained tools; age alone refuses nothing, abandonment does) and drafts the profile in the
  engine's format, `status = "provisional"`, with its agent-conventions file, into
  `docs/blueprint/proposals/`. The bead names the draft; the shelf session adopts it.

## 7. Survey (end of every run)

Copy the questions of `survey.toml` (in the blueprint package) into `docs/blueprint/survey.md`, one table per
section (`id | question | answer | evidence`), and answer every row from the file's closed `answers` set with one line of
evidence. Answer as a critic of
the run: a "yes" without evidence is a "partly".

**No run ends without the relay.** The shelf improves only from what comes back, and people forget.
Your last message ends with a block the owner pastes into a shelf session, unless the harness can
send it there itself (Claude desktop: a message to the shelf's session), in which case send it and
say so in one line:

```
Blueprint run on <repo> (<date>, checkpoint set <hash>): improve blueprint from it.
Survey: <absolute path to docs/blueprint/survey.md> (non-yes rows: <ids>)
Beads filed in the shelf: <ids, one-line titles, wrong verdicts first>
Profile drafts: <paths in docs/blueprint/proposals/, or none>
Friction no checkpoint covers: <one line each, or none>
```

## 8. Agentic delivery audit

On request ("audit how agents build and test here"), or when the repo runs an agent loop: judge it against
[agentic-delivery.md](agentic-delivery.md) (roles, agent context, test layers and cost, test radius, machine speed,
determinism, review, gate). The engine does not check these rules yet; the audit is by evidence, row by row, as that
file's §10 says. Its ❌ rows become beads like any other finding.

## Gotchas

- Writing ✅ for a row the engine reported otherwise is the failure this skill exists to prevent.
- Hooks: never let bd install its own (`bd init --skip-hooks`; `bd hooks install` never). bd's
  hooks run from `.pre-commit-config.yaml` via prek; bd's own injection makes a failing check stop
  blocking commits in other managers' hook files.
- `--audit` adds the audit-only rows: slow ones (a fresh clone running `just check`) and ones
  reading this clone's state (installed hooks, bd's database). The repo's `just blueprint` skips them.
- Decision records, the glossary and the agent docs are not blueprint's: `python -m any_knowledge` (`index`, `check`, `seed`) keeps them.
- Concerns: `gate`, `backlog`, `secrets`, `stack`, `framework`, `agents`; profiles python-uv
  (evidenced); node, go, rust, dotnet, nix, compose, dockerfile, shell, godot, unity and mcp (provisional). A mixed repo gets one table per stack and declares the edges between them. A repo with no code yet
  declares its stack (`[profile] stacks = ["python-uv"]` in docs/blueprint/blueprint.toml). Do not invent rows for what the engine does not check.
- ADRs are living: one file per decision topic, rewritten when it changes, the dropped decision and
  why in its `## History`. `python -m any_knowledge index --write` regenerates the index agents read.
- Two projects of one framework (a game and a prototype spike) each get a table; the owner names
  the real one in `docs/blueprint/blueprint.toml` (`[profile.frameworks] godot = "src/Game.Godot"`).
