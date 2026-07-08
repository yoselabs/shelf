# AGENTS.md — shelf working agreement

## §1. Definition of Done

A task is **done** only when the full quality gate passes across the **entire repo** —
not just the files the task touched:

```bash
make check    # ruff check + ruff format + ty (--error-on-warning) + codespell + deptry + pytest/coverage
```

**No carve-outs.** "Pre-existing drift", "unrelated file", or "that's a separate change"
do **not** satisfy Done. If `make check` is red for any reason, the task is not finished. This
toolchain is the **reference every consumer inherits** (`docs/linting.md`, resolution 0004).

## §2. The constitution governs

Read `docs/constitution.md` before changing anything. The load-bearing rules:

- **Files are truth; indexes are derived.** Never hand-edit a catalog/index — project it.
- **One concept per file** (one use case, one contract, one primitive) → conflict-free parallel work.
- **Structure controls size, not caps.** A big file = a missing boundary, not a lint failure.
- **Protection is earned.** A contract is born `candidate` (inert) until a live consumer breaks
  without it. Do NOT protect on fear.
- **Adopt conservatively, promote aggressively** (res 0006). *Pulling* a shelf dep: only if
  DEEP·STABLE·WINS, else duplicate. *Writing* generic substrate: promote it to the shelf in the moment
  (extracted, never invented) — a self-assessed "feels reusable" is enough, no 2nd consumer needed.
- **Decay + reconciliation are mandatory.** Unreused past TTL → deprecate. A recurring reconciliation pass
  merges/splits/deletes/demotes the aggressively-promoted catalog with hindsight. Deletion is a virtue.

## §3. The one invariant

A shelf package **must not import any consumer app** (a2kay, a2web, a2kit, …). Enforced by
`tests/test_boundary.py`. If you need a consumer's type, you have the arrow backwards.

## §4. Conventions

- Tests-first (BDD/TDD): the failing test (a use-case scenario) before the implementation.
- Versions are **git tags**, namespaced per package (`anyllm-v0.2.0`). Never delete an old tag.
- Changes go through OpenSpec (`openspec/changes/<name>/`): proposal → design → tasks → apply → archive.
- The shelf never imports a2kay's substrate; a2kay is a *donor of ideas* and the *first consumer*, nothing more.
