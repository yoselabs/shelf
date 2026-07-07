# shelf

The shared home of small, individually-**ownable**, **composable**, **contract-guaranteed**
software pieces — reused across separate apps (a2kay, a2web, …) instead of re-written.

*(Working name — branding deferred. The differentiator is ownability + composability +
contract-guarantee, not "micro"/smallness.)*

## What lives here

- `packages/` — the software. Each is a uv-workspace member, versioned by **git tag**
  (`anyllm-v0.2.0`). Consumers in other repos pin `{ git, subdirectory, tag }`. No PyPI.
- `docs/constitution.md` — the 8 load-bearing rules.
- `docs/glossary.md` — the ontology (TYPES only, never instances).
- `docs/` — thoughts → tracks → missions → resolutions (see `docs/resolutions/README.md`).
- `tests/` — repo-level fitness tests (the boundary spine: no package may import a consumer).

## The one law that keeps this reusable

A shelf package **never imports a consumer app**. The dependency arrow points UP into the
apps, never down out of them. Enforced by `tests/test_boundary.py`.

## Quality gate

```
make check   # ruff check + ruff format --check + ty + pytest, whole-repo, no carve-outs
```

## Provenance

The founding doctrine and the full bootstrap exploration:
`docs/thoughts/2026-07-07-shelf-exploration.md` — read it first if you are a fresh session.
