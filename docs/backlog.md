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
  files exist. Deepest value; still inert — its previously-cited trigger (`convert-md`'s `convert_html`
  string-input capability) has already shipped and been adopted by a2web (2026-07-09 check) *without*
  a contract file, so that trigger fired and passed with nothing built. Needs a fresh, concrete trigger
  before starting — do not build on the old citation alone.
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
- [ ] **a2web adopts `anyllm.ProviderName` (decided direction, unbuilt).** `anyllm-v0.3.0` (ledger 0037)
  added a `StrEnum` on the shelf side; a2web's plugin-registry keys (`"anthropic"`, `"claude-code"`) and
  `ProviderMode` Literal (`settings.py:30`) are a *different* string set — not cosmetic drift, so this
  isn't a mechanical rename. Decided 2026-07-09: **adopt, not just align** — that's the only way to get
  drift-safety on future anyllm releases. Reasoning, for the a2web session that picks this up:
  - Bumping anyllm's pin alone can't force a2web to notice a new provider — `build_adapter(provider: str,
    ...)` stays loosely typed *on purpose* (it's a config-ingestion boundary; YAML/env are always
    strings, so `ty` can't help there, and the function already validates at runtime). Static
    drift-detection has to live in the *consumer's* typed code, not the library's boundary function.
  - The fix: a2web parses its config string into `ProviderName` **once**, at the settings field itself —
    `ProviderMode = Literal[...]` → `provider: ProviderName` on the `pydantic_settings.BaseSettings`
    field. `StrEnum` is natively a pydantic validator; no custom `field_validator` needed. Everything
    downstream in a2web becomes `ProviderName`-typed for free.
  - Payoff: an exhaustive `match`/`case` (`assert_never` on the fallback, no wildcard) anywhere
    downstream then gets `ty`-checked — a future anyllm provider added without a matching a2web branch
    fails typecheck on `make check`, not silently at runtime.
  - The one real design decision buried in the rename: a2web's plugin registry currently has **one**
    `"claude-code"` plugin where anyllm distinguishes `CLAUDE_CODE_CLI` vs `CLAUDE_CODE_SDK` — decide
    whether a2web wants both exposed as separate plugins or deliberately collapses them, don't let the
    rename paper over that.
  - `PluginManifest.name` is a public lookup key (`registry["anthropic"]`) — ships as a breaking change,
    per `RECEIVE` step 4 ("migrate to the new idiom, not the smallest diff... delete compat shims").

## Promote — generic substrate to capitalize (res 0006; done in each app's catch-up sweep)

Under aggressive promotion these are no longer "wait for a 2nd consumer" — they are generic substrate to
extract now, in the origin app's session (worktree `../shelf-<app>`), born `candidate`:

- **a2kay's T0 primitives** `atomic_io`, `duckdb_sidecar`, `managed_region` — generic substrate, promote
  in a2kay's catch-up. (Was parked at n=1; res 0006 removes that gate.)
- **a2web's generic utilities** — env/YAML settings loader, sqlite conditional-GET cache shell,
  cookie-store matrix, collection/JSON helpers. Promote the generic ones; **leave the product moat**
  (bot-wall detection, proxy routing, browser backends) in a2web.

## Parked — captured, build later

- **Onboarding `catalog`/`onboard` skill** — the judgment layer; runbook is built
  ([mission](missions/onboarding-new-micro-software.md)), the skill is not.

## Gaps

- [ ] **Guard enforcement is per-clone.** Onboarding installs the hook in one command
  (`tools/hooks/install.py`, §2), but git hooks can't be committed, so a fresh clone is unguarded until
  someone runs it. **Trigger:** a 2nd machine/clone, OR the first leaked override — then fold a
  working-tree check into `make check` (or enforce in CI).
