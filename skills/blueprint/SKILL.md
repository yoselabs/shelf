---
name: blueprint
description: The shelf's standard for every software repository — start a new repo, or audit an existing one, against it. Runs the blueprint check engine over the repo, writes a verdict table per concern to docs/blueprint/, proposes a remediation per finding (auto, agent or owner), and applies them only after the owner's yes. Invoke as /blueprint in the repository to judge.
disable-model-invocation: true
---

# blueprint

**Resume rule:** after compaction or a new session, re-invoke `/blueprint`, read
`docs/blueprint/*.md` in the repo, and continue from the first row that is not ✅.

**Verdicts** (one per checkpoint, from the engine, never from your judgment):
`not set up` · `failing` · `passing` · `not applicable` · `not checked`.
`not checked` is never a pass. You do not write a verdict the engine did not print.

**Directions:**

| direction | when | changes the repo? |
|---|---|---|
| audit (default) | `/blueprint`, `/blueprint audit` | only `docs/blueprint/*.md` |
| remediate | the owner says yes to the plan an audit showed | yes |
| start | `/blueprint start`, or the repo has no commits | yes, after the owner's yes: audit of the empty repo, then remediate |
| reabsorb | `/blueprint reabsorb`, or a run met something no checkpoint covers | files beads in the shelf, never in the repo |

## 1. Find the engine

The engine is `packages/blueprint` in the shelf. Use the first that exists:
`${CLAUDE_SKILL_DIR}/../../packages/blueprint/src`, `$SHELF_HOME/packages/blueprint/src`,
`../shelf/packages/blueprint/src`, `~/Workspaces/shelf/packages/blueprint/src`.
For a clone, first `git -C <shelf> pull --ff-only`; if that fails, say so in one line and go on.

```bash
PYTHONPATH=<engine> python3 -m blueprint check --repo . --audit --json
```

Exit 0 all pass · 1 something fails or is not set up · 2 something could not be checked.
Python 3.11+ only; nothing to install.

## 2. Audit

1. Run the engine with `--audit --json`, then again with `--audit --write` for the report files.
2. For each `not checked` row, find why (a missing tool, no commits). Fix the cause only when it
   is outside the repo and harmless (installing nothing without asking); otherwise it stays a row.
3. Show the owner the plan (§4). Stop. Nothing else in the repo changes before the yes.

## 3. Remediate (after the owner's yes)

Order: `auto` rows first (the engine's remediation text is a command or an exact edit), then
`agent` rows, one concern at a time. After each concern, re-run the engine for that concern
(`--concern X --audit`). A remediation that never turned its row ✅ is unverified: say so.

- `owner` rows go to the owner as one batched question round, each with your default, worded
  so "yes" accepts it. Never decide them yourself.
- A row that is right to leave failing becomes an override in `docs/blueprint/blueprint.toml`
  (code, reason, expiry), only with the owner's yes. Codes: `test-data` · `remediated` ·
  `not-applicable` · `not-supported` · `not-detected`.
- Every row still not ✅ at the end becomes a bead in the repo's tracker, its id in the title.
- Finish with the repo's own `make check` green, then `--write` again so the reports match.

## 4. Output contract

Reports are tables, never prose. The chat gets, after the report files are written, only:
decisions that are the owner's, mistakes that reached him, and work ready for his yes.

The plan, in chat:

| | checkpoint | why it fails | remediation | by |
|---|---|---|---|---|
| ❌ | `gate.ci` | actions pinned by tag | pin each to a SHA | auto |

- Marks carry meaning only: ✅ passing · ❌ failing or not set up · ⚠️ needs the owner ·
  🔒 not checked. One per row.
- Opener ≤10 words, one clause. Every label the owner has not used himself gets a one-clause
  gloss by its job on first use. A hedge survives shortening.
- Large or structural change (new layers, a moved test tree, a new folder layout): a short
  plain-words explanation first; when much work is ahead, an Artifact page with the target
  folder structure, layers, test structure and main design as diagrams.

## 5. Start a new repo

Audit the empty repo (every row `not set up`), show the plan, and on the yes remediate in this
order: tracker (`bd init`, strict settings) → gate (`make check` that resolves, hooks, CI) → the
rest. For a Python repo the shelf onboarding writes most of the gate:
`python3 <shelf>/.agents/skills/onboard-consumer/scripts/onboard.py --repo .`.

## 6. Reabsorb

When a run meets something the engine does not cover — a defect the owner cares about, a setup
choice with no checkpoint — file one bead in the **shelf** (`bd create` in the shelf clone) titled
`blueprint lacks: <what>`, with the repo, the evidence and the checkpoint you would add. Never add
the checkpoint inside the consumer.

## Gotchas

- The engine judges; you remediate. Writing ✅ for a row the engine reported otherwise is the
  failure this skill exists to prevent.
- `--audit` adds the audit-only rows: slow ones (`gate.clean-clone` clones and runs
  `make check`) and ones reading this clone's own state (hooks, bd's database). The repo's own
  `make blueprint` leaves them out.
- v0.1 covers the `gate` and `backlog` concerns. Say so in the report; do not invent rows for
  concerns the engine does not check.
