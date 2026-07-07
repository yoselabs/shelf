# shelf — start here

The shared home of small, **ownable**, **composable**, **contract-guaranteed** software pieces,
reused across separate apps (a2kay, a2web, …) instead of re-written. Working name; branding deferred.

This file is the map. Everything the shelf knows about itself is in this repo — links below.

## Read in this order

1. **[docs/doctrine.md](docs/doctrine.md)** — the *why*: what the shelf is and the load-bearing ideas.
2. **[docs/constitution.md](docs/constitution.md)** — the 8 operating rules that follow from the doctrine.
3. **[docs/glossary.md](docs/glossary.md)** — the ontology / vocabulary (**types only**, never instances).
4. **[AGENTS.md](AGENTS.md)** — the working agreement: Definition of Done, conventions, the one invariant.

## Consuming & contributing

- **[docs/consuming-the-shelf.md](docs/consuming-the-shelf.md)** — how a project onboards as a consumer
  (depend by git+tag, paste the directive into its own `AGENTS.md`/`CLAUDE.md`).
- **Contribute back** via *promotion, not publication*: a piece graduates when a **2nd** consumer pulls
  it. Read [docs/constitution.md](docs/constitution.md) (Articles VI–VIII) first.

## Decisions & open work

- **[docs/resolutions/](docs/resolutions/)** — decided things (ADR-style, each with an expiry).
  Start: [0001 — repo topology](docs/resolutions/0001-repo-topology.md). Flow explained in the
  [resolutions README](docs/resolutions/README.md) (thoughts → tracks → missions → resolutions).
- **[docs/missions/](docs/missions/)** — scoped future objectives, e.g.
  [onboarding new micro-software](docs/missions/onboarding-new-micro-software.md) (runbook + skill, to build).
- **[docs/thoughts/](docs/thoughts/)** — the origin exploration (kept, not authoritative):
  [2026-07-07 shelf exploration](docs/thoughts/2026-07-07-shelf-exploration.md) — the full brain-dump + all 11 resolutions.

## The packages

`packages/` — the software (uv-workspace members), versioned by **git tag** (`anyllm-v0.1.0`).
Today: `anyllm`, `anyembed`, `convert-md`, `git-porcelain`.

## The one invariant

A shelf package **never imports a consumer app** (a2kay, a2web, …). The dependency arrow points UP into
the apps, never down out of them. Enforced by [tests/test_boundary.py](tests/test_boundary.py).

## Quality gate

```
make check   # ruff check + ruff format --check + ty + pytest — whole-repo, no carve-outs
```

## Still open (see the exploration doc for full context)

- `openspec init` here (docs-as-system built; openspec not wired yet).
- Dev-loop override — an uncommitted `uv.toml` path source for co-editing shelf + a consumer.
- Onboarding runbook + `catalog`/`onboard` skill (captured in `docs/missions/`).
