# AGENTS.md — shelf: start here

The shared home of small, **ownable**, **composable**, **contract-guaranteed** software pieces,
reused across separate apps (a2kay, a2web, …) instead of re-written. Working name; branding deferred.

This file is the map and the working agreement. It carries only *structurally stable* knowledge —
the rules and where things live. It never mirrors evolving instance data (the package roster, the
open backlog, fitness records): those have derived homes, linked below, and are the source of truth.
If you catch this file naming a specific package count or roster, that's a bug — delete it.

> This is the canonical agent instructions file (read by Claude Code, opencode, Codex, …).
> `CLAUDE.md` is a symlink to it — edit only this file.

## Read in this order

1. **[docs/doctrine.md](docs/doctrine.md)** — the *why*: what the shelf is and the load-bearing ideas.
2. **[docs/constitution.md](docs/constitution.md)** — the 8 operating rules that follow from the doctrine.
3. **[docs/glossary.md](docs/glossary.md)** — the ontology / vocabulary (**types only**, never instances).
4. **§ The working agreement** (below) — Definition of Done, conventions, the one invariant.

## The working agreement

### Definition of Done

A task is **done** only when the full quality gate passes across the **entire repo** —
not just the files the task touched:

```bash
make check    # ruff check + ruff format + ty (--error-on-warning) + codespell + deptry + pytest/coverage
```

**No carve-outs.** "Pre-existing drift", "unrelated file", or "that's a separate change" do **not**
satisfy Done. If `make check` is red for any reason, the task is not finished. This toolchain is the
**reference every consumer inherits** ([docs/linting.md](docs/linting.md), a config-preset not a CLI —
[resolution 0004](docs/resolutions/0004-linters-are-a-config-preset.md)).

### The constitution governs

Read [docs/constitution.md](docs/constitution.md) before changing anything. The load-bearing rules:

- **Files are truth; indexes are derived.** Never hand-edit a catalog/index — project it. (This
  applies to *this file too*: don't paste evolving instance data here.)
- **One concept per file** (one use case, one contract, one primitive) → conflict-free parallel work.
- **Structure controls size, not caps.** A big file = a missing boundary, not a lint failure.
- **Protection is earned.** A contract is born `candidate` (inert) until a live consumer breaks
  without it. Do NOT protect on fear.
- **Adopt conservatively, promote aggressively** ([res 0006](docs/resolutions/0006-aggressive-capitalization-reconcile-later.md)).
  *Pulling* a shelf dep: only if DEEP·STABLE·WINS, else duplicate. *Writing* generic substrate: promote
  it to the shelf in the moment (extracted, never invented) — a self-assessed "feels reusable" is
  enough, no 2nd consumer needed.
- **Decay + reconciliation are mandatory.** Unreused past TTL → deprecate. A recurring reconciliation
  pass merges/splits/deletes/demotes the aggressively-promoted catalog with hindsight. Deletion is a
  virtue.

### The one invariant

A shelf package **must not import any consumer app** (a2kay, a2web, a2kit, …). The dependency arrow
points UP into the apps, never down out of them. Enforced by
[tests/test_boundary.py](tests/test_boundary.py). If you need a consumer's type, you have the arrow
backwards — a2kay is a *donor of ideas* and the *first consumer*, nothing more.

### Conventions

- Tests-first (BDD/TDD): the failing test (a use-case scenario) before the implementation.
- Versions are **git tags**, namespaced per package (`anyllm-v0.2.0`). Never delete an old tag.
- Changes go through **OpenSpec** (`openspec/changes/<name>/`): proposal → design → tasks → apply →
  archive. Project context for the AI lives in [openspec/config.yaml](openspec/config.yaml).

## How the repo is organized

- **`packages/`** — the software (uv-workspace members), versioned by **git tag** (`anyllm-v0.1.0`).
  The live roster is [catalog/README.md](catalog/README.md) (derived — do not look for it here).
- **The ontology** (flat files, [resolution 0003](docs/resolutions/0003-ontology-lives-as-flat-files.md)) —
  instance data, projected into READMEs by `make catalog` (never hand-edit the READMEs):
  - `catalog/` — one manifest per MicroSoftware (supply). `catalog/README.md` is derived.
  - `use-cases/` — one file per (consumer × software): each consumer **publishes** why it depends and
    what it needs. Consumers are *derived* from these; zero active ⇒ orphaned (constitution Article VIII).
  - `ledger/` — the append-only fitness record (request → delivery → verdict → cost).

## Consuming & contributing

- **[docs/consuming-the-shelf.md](docs/consuming-the-shelf.md)** — how a project onboards as a consumer
  (depend by git+tag, install the commit guard, paste the resolver block into its `AGENTS.md`).
- **[docs/agent-loop.md](docs/agent-loop.md)** — the standing loop every consumer's agent self-applies:
  fetch cadence, adopt-vs-promote, promote-in-the-moment, the promote procedure, RECONCILE, escape hatch.
- **Contribute back** by **promoting aggressively** ([res 0006](docs/resolutions/0006-aggressive-capitalization-reconcile-later.md)):
  the moment you write generic substrate, home it in the shelf (extracted, never invented) — no 2nd
  consumer needed; reconcile later. Read the constitution (Articles VI–VIII) first.

## Decisions, open work, and the backlog

**`backlog` = `kanban` = `beads`.** One mechanism, three names that all mean `bd`. There is no
backlog file and no board — `docs/backlog.md` was migrated into beads on 2026-08-12 and deleted.
Don't go looking for it, and don't start a replacement.

- **`bd ready`** — the single curated view of what's actionable (`bd list --all` for everything,
  including deferred). Close beads as they finish; the git log plus the ledger are the record.
- **[docs/resolutions/](docs/resolutions/)** — decided things (ADR-style, each with an expiry).
  Start: [0001 — repo topology](docs/resolutions/0001-repo-topology.md). Flow explained in the
  [resolutions README](docs/resolutions/README.md) (thoughts → tracks → missions → resolutions).
- **[docs/missions/](docs/missions/)** — scoped future objectives.
- **[docs/thoughts/](docs/thoughts/)** — the origin exploration (kept, not authoritative).

### Beads conventions (this repo's own — not part of bd's managed blocks below)

Two blocks below are generated and maintained by `bd` (one for Claude, one for Codex — near
duplicates; that's bd's doing, not drift). **These rules override them where they conflict:**

- **Do NOT use `bd remember` / `bd prime` for persistent memory.** The operator already runs a
  memory system; a fourth one fragments it. bd's blocks say otherwise — this line wins. Use `bd`
  for *work tracking only*.
- **Three distinct "not ready" states — don't collapse them** (see
  [docs/runbooks/adopt-beads.md](docs/runbooks/adopt-beads.md) §1.3):

  | Situation | Mechanism |
  |---|---|
  | Waiting on another tracked bead | `bd dep add <id> <blocker> --type blocks` — status stays `open`; surfaced by `bd blocked` |
  | Deliberately shelved, nothing specific blocking it | `bd defer <id> --reason "<the trigger>"` |
  | Waiting on something with no bead (external access, a human decision) | `bd update <id> --status blocked` + a comment; find via `bd list --status blocked`, **not** `bd blocked` |

  Never invent a synthetic blocking bead for "not started yet" — that's `deferred`.
- **Gated work carries its trigger in the defer reason.** This repo's doctrine is "do NOT build on
  spec" — a deferred bead whose reason doesn't name a concrete trigger is incomplete.
- **Link a bead to a mission/resolution** with `bd update <id> --spec-id "<path>"` (a native field,
  not free text). **Branch/commit provenance:** `bd update <id> --set-metadata branch=<name>
  --set-metadata commit=<sha>` — a convention, not a bd feature. **Supersession:**
  `bd dep add <new> <old> --type supersedes`, never delete the superseded bead.
- **`bd config set` edits `.beads/config.yaml`, which is a tracked file.** A `git checkout` or
  `git reset --hard` silently reverts your config. Always confirm with `bd config get <key>`.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:970c3bf2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   bd dolt push
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

<!-- BEGIN BEADS CODEX SETUP: generated by bd setup codex -->
## Beads Issue Tracker

Use Beads (`bd`) for durable task tracking in repositories that include it. Use the `beads` skill at `.agents/skills/beads/SKILL.md` (project install) or `~/.agents/skills/beads/SKILL.md` (global install) for Beads workflow guidance, then use the `bd` CLI for issue operations.

### Quick Reference

```bash
bd ready                # Find available work
bd show <id>            # View issue details
bd update <id> --claim  # Claim work
bd close <id>           # Complete work
bd prime                # Refresh Beads context
```

### Rules

- Use `bd` for all task tracking; do not create markdown TODO lists.
- Run `bd prime` when Beads context is missing or stale. Codex 0.129.0+ can load Beads context automatically through native hooks; use `/hooks` to inspect or toggle them.
- Keep persistent project memory in Beads via `bd remember`; do not create ad hoc memory files.

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.
<!-- END BEADS CODEX SETUP -->
