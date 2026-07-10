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

- **[docs/backlog.md](docs/backlog.md)** — the single curated view of what's left (traces to verify,
  gated builds, open decisions, parked items). Prune lines as they close; the git log is the record.
- **[docs/resolutions/](docs/resolutions/)** — decided things (ADR-style, each with an expiry).
  Start: [0001 — repo topology](docs/resolutions/0001-repo-topology.md). Flow explained in the
  [resolutions README](docs/resolutions/README.md) (thoughts → tracks → missions → resolutions).
- **[docs/missions/](docs/missions/)** — scoped future objectives.
- **[docs/thoughts/](docs/thoughts/)** — the origin exploration (kept, not authoritative).
