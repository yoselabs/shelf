# shelf backlog

A **curated index**, not a source of truth — each item points at its authoritative home
(`R…` = a section of the exploration [thoughts doc](thoughts/2026-07-07-shelf-exploration.md);
`mission` / `resolution` = the track docs). **Prune, don't accumulate** (constitution III): when an
item is done, *delete its line* — the git history is the record. A growing backlog that no one prunes
is a smoke alarm.

## Verify — designed & shipped, never triggered end-to-end (highest risk)

- [ ] **Promote → tag → repoint → opt-in upgrade, for one real package.** The 4 packages were
  bootstrapped, not promoted through the loop; the cycle is theory until one package walks it.
  (`agent-loop.md` §4–5.)
- [ ] **`convert-md`'s docx engine choice (pandoc over markitdown) is reasoned, not verified.** Kept for
  one concrete reason — pandoc's `--track-changes=all` preserves tracked-changes/redline metadata,
  which markitdown's plain-text extraction can't replicate — but unlike PDF (bench/results/
  2026-07-09-findings.md), no docx corpus exists in `bench/` to actually test it. Surfaced 2026-07-09
  during the PDF-engine work. Build the same evidence-backed treatment if/when it matters.

## Build — designed, unbuilt, gated (do NOT build on spec)

- [ ] **Contract layer + `Implementation` build-vs-adopt harness (the crown insight).** No contract
  files exist. Deepest value; inert until a real contract need appears — the first live one is
  `convert-md`'s string-input capability (see Promote below).
  [mission](missions/contract-and-implementation-harness.md). (R2/R3, glossary.)
- [ ] **Reconciliation-pass tooling.** Aggressive promotion (res 0006) makes reconciliation load-bearing
  (constitution VIII, agent-loop §5b): merge/split/delete/demote the catalog with hindsight. Today it is
  a manual walk of `catalog/README.md` + `make advisory`; a `make reconcile` that flags overlap
  (cross-package body-dup), zero-use pieces, and kitchen-sinks would make it routine. Build once the
  catalog is large enough to need it.
- [ ] **Remaining architectural rules: layer-DAG + no-`dict[str,Any]`.** The core trio (body-dup,
  private-name-collision, dep-upper-bound) is **built native** (resolution 0005, `tools/arch_rules.py`).
  Still un-ported from a2kit: the import layer-DAG and the `dict[str,Any]`-ban. Add as fitness tests
  when a real layering/typing violation appears. (R9.)
- [ ] **Expired-resolution advisory check.** `docs/resolutions/*.md` frontmatter already carries an
  `Expires:` date; nothing reads it. Extend `make advisory` (non-blocking, like the cross-package
  duplication check) to flag resolutions past their expiry at a reconciliation pass. Not
  commit-blocking — date-triggered, not diff-triggered.

## Decide — open forks (a decision, not a build)

- [ ] **release-please** adoption timing. **Trigger:** the *first* tag/changelog bookkeeping mistake, OR
  a 2nd human contributor. Until then manual `git tag` at n=4 packages is fine. (R§6.5.)
- [ ] **Branding** — parked on purpose (user: dislikes both "shelf" and "microsoftware"; rename later).
  A separate pass, no throwaway names. (R11.)
- [ ] **a2web's provider vocabulary vs. `anyllm.ProviderName`.** `anyllm-v0.3.0` (ledger 0037) added a
  `StrEnum` on the shelf side, but a2web's plugin-registry keys (`"anthropic"`, `"claude-code"`) and its
  `ProviderMode` Literal are a *different* string set, not the same vocabulary under different names —
  collapsing onto anyllm's values would rename a2web's public config surface, a breaking change. Undecided
  whether that rename is worth it; surfaced 2026-07-09.

## Promote — generic substrate to capitalize (res 0006; done in each app's catch-up sweep)

Under aggressive promotion these are no longer "wait for a 2nd consumer" — they are generic substrate to
extract now, in the origin app's session (worktree `../shelf-<app>`), born `candidate`:

- **a2kay's T0 primitives** `atomic_io`, `duckdb_sidecar`, `managed_region` — generic substrate, promote
  in a2kay's catch-up. (Was parked at n=1; res 0006 removes that gate.)
- **a2web's generic utilities** — env/YAML settings loader, sqlite conditional-GET cache shell,
  cookie-store matrix, collection/JSON helpers. Promote the generic ones; **leave the product moat**
  (bot-wall detection, proxy routing, browser backends) in a2web.
- **`convert-md` → add a `convert_html(str, *, url) -> ConversionResult` capability** — the first real
  friction-driven contract evolution (a2web holds HTML in memory, not on disk). Extend, then a2web adopts.

## Parked — captured, build later

- **Onboarding `catalog`/`onboard` skill** — the judgment layer; runbook is built
  ([mission](missions/onboarding-new-micro-software.md)), the skill is not.

## Gaps

- [ ] **Guard enforcement is per-clone.** Onboarding installs the hook in one command
  (`tools/hooks/install.py`, §2), but git hooks can't be committed, so a fresh clone is unguarded until
  someone runs it. **Trigger:** a 2nd machine/clone, OR the first leaked override — then fold a
  working-tree check into `make check` (or enforce in CI).
