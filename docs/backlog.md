# shelf backlog

A **curated index**, not a source of truth — each item points at its authoritative home
(`R…` = a section of the exploration [thoughts doc](thoughts/2026-07-07-shelf-exploration.md);
`mission` / `resolution` = the track docs). **Prune, don't accumulate** (constitution III): when an
item is done, *delete its line* — the git history is the record. A growing backlog that no one prunes
is a smoke alarm.

## Verify — designed & shipped, never triggered end-to-end (highest risk)

- [ ] **`convert-md`'s HTML render path is one converter, unverified across real pages.** The docx
  work (docx-engine-verification, design.md D7) established that `convert_html`'s `web_page` kind
  uses trafilatura (extraction) and `clean` uses html2text (faithful render). Only html2text's clean
  path is now exercised widely (via docx). Whether trafilatura is the *best* web extractor, and
  whether html2text vs markdownify is the *right* canonical clean renderer, is untested on a real
  web corpus — and it touches a2web's live path. A `WORKFLOW: BENCH` run (resolution 0011) with a
  real-web corpus is the proper treatment; build when it matters. (docx-verify itself: closed
  2026-07-10, bench/results/2026-07-10-docx-findings.md — pandoc dropped for mammoth.)

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

## Parked — captured, build later

- **Onboarding `catalog`/`onboard` skill** — the judgment layer; runbook is built
  ([mission](missions/onboarding-new-micro-software.md)), the skill is not.

## Gaps

- [ ] **Guard enforcement is per-clone.** Onboarding installs the hook in one command
  (`tools/hooks/install.py`, §2), but git hooks can't be committed, so a fresh clone is unguarded until
  someone runs it. **Trigger:** a 2nd machine/clone, OR the first leaked override — then fold a
  working-tree check into `make check` (or enforce in CI).
