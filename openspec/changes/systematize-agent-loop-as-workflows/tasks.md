## 1. Draft the workflow inventory (content, before formatting)

- [x] 1.1 Line up every existing rule in the current `agent-loop.md` (§1–§7) against the new
      workflow inventory (design.md D2) — checklist proving nothing is dropped
- [x] 1.2 Draft `WORKFLOW: SESSION-RESOLVE` (folds current §1 + the clone-if-absent step from
      `consuming-the-shelf.md`'s resolver block), including the staleness bound (D4)
- [x] 1.3 Draft `WORKFLOW: SEAM` (current §2, four directions — reformat only)
- [x] 1.4 Draft `WORKFLOW: PROMOTE` (current §3 posture folded in + §4 procedure), with the
      worktree-freshness step first (D5) and the CHANGELOG.md requirement (D6)
- [x] 1.5 Draft `WORKFLOW: RECEIVE` (current §5), with the "read CHANGELOG.md first" step
- [x] 1.6 Draft `WORKFLOW: RECONCILE` (current §5b — reformat only)
- [x] 1.7 Draft `WORKFLOW: ESCAPE-HATCH` (current §6 — reformat only)
- [x] 1.8 Draft `WORKFLOW: EVOLVE-THE-LOOP` (new, design.md D3)
- [x] 1.9 Keep §7 ("what is NOT in this loop") as closing prose, unchanged in substance

## 2. Rewrite agent-loop.md

- [x] 2.1 Replace `docs/agent-loop.md` body with the drafted workflow blocks (D1 format), in the
      order: SESSION-RESOLVE, SEAM, PROMOTE, RECEIVE, RECONCILE, ESCAPE-HATCH, EVOLVE-THE-LOOP,
      closing note
- [x] 2.2 Preserve the file's opening framing paragraph (what this file is, "read once per
      session, lazily, cache it") — it's not a workflow, it's the file's own header
- [x] 2.3 Cross-check against task 1.1's checklist — every prior rule present in a step

## 3. Resolution distillation field

- [x] 3.1 Add `Distilled into:` to the resolution template in `docs/resolutions/README.md`
- [x] 3.2 Backfill `docs/resolutions/0001-repo-topology.md`
- [x] 3.3 Backfill `docs/resolutions/0002-doctrine-homes-in-the-shelf.md`
- [x] 3.4 Backfill `docs/resolutions/0003-ontology-lives-as-flat-files.md`
- [x] 3.5 Backfill `docs/resolutions/0004-linters-are-a-config-preset.md`
- [x] 3.6 Backfill `docs/resolutions/0005-architecture-rules-are-native-fitness-tests.md`
- [x] 3.7 Backfill `docs/resolutions/0006-aggressive-capitalization-reconcile-later.md`
      (→ `agent-loop.md#workflow-seam` / `#workflow-promote`)
- [x] 3.8 Backfill `docs/resolutions/0007-evolve-on-monotonic-contracts.md`
      (→ `agent-loop.md#workflow-seam`)

## 4. Blocking test for the distillation field

- [x] 4.1 Write `tests/test_resolution_distillation.py`, mirroring
      `tests/test_catalog_projection.py`'s pattern: iterate `docs/resolutions/*.md`, assert a
      non-empty `Distilled into:` frontmatter line on each
- [x] 4.2 Run it against the backfilled resolutions (task 3) — must pass

## 5. Package CHANGELOG.md convention

- [x] 5.1 Write `packages/anyllm/CHANGELOG.md` — `## 0.2.0` entry, arrow-notation, sourced from
      the README's existing migration table and `ledger/0032-anyllm-v2-delivered.toml`
- [x] 5.2 Confirm `WORKFLOW: RECEIVE` (task 1.5) references it correctly

## 6. Verify

- [x] 6.1 `make check` green (includes the new test from task 4)
- [x] 6.2 Re-read the rewritten `agent-loop.md` top to bottom as if a fresh consumer session —
      confirm every workflow is self-contained (trigger, steps, output) with no forward references
      to prose that no longer exists
- [ ] 6.3 Commit and push (per user's no-PR convention for this repo)
