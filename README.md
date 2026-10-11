# shelf

The shared home of small, individually-**ownable**, **composable**, **contract-guaranteed**
software pieces — reused across separate apps (a2kay, a2web, …) instead of re-written.

*(Working name — branding deferred. The differentiator is ownability + composability +
contract-guarantee, not "micro"/smallness.)*

## What lives here

- `packages/` — the software. Each is a uv-workspace member, versioned by **git tag**
  (`anyllm-v0.2.0`). Consumers in other repos pin `{ git, subdirectory, tag }`. No PyPI.
- `docs/doctrine.md` — the *why*: what the shelf is and the load-bearing ideas.
- `docs/constitution.md` — the 8 load-bearing rules.
- `CONTEXT.md` — the ontology (TYPES only, never instances).
- `docs/` — thoughts → tracks → missions → ADRs (see `docs/adr/README.md`; the list is `docs/adr/INDEX.md`).
- `tests/` — repo-level fitness tests (the boundary spine lives in `[tool.importlinter]`, run by `make arch`; these tests guard it and the AST rules).

## The one law that keeps this reusable

A shelf package **never imports a consumer app**. The dependency arrow points UP into the
apps, never down out of them. Enforced by the import-linter `forbidden` contract in `pyproject.toml` (`make arch`).

## Quality gate

```
make check   # ruff check + ruff format --check + ty + pytest, whole-repo, no carve-outs
```

## Provenance

The founding doctrine and the full bootstrap exploration:
`docs/thoughts/2026-07-07-shelf-exploration.md` — read it first if you are a fresh session.
