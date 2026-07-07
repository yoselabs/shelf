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
- [ ] **Pre-commit-*framework* path.** The one-command installer (native hook) is tested and is the
  onboarding default; the `.pre-commit-hooks.yaml` `rev:` wiring (the framework alternative) has never
  been resolved by a real consumer.

## Build — designed, unbuilt, gated (do NOT build on spec)

- [ ] **Contract layer + `Implementation` build-vs-adopt harness (the crown insight).** No contract
  files exist. Deepest value; inert until a real 2nd consumer / contract need appears.
  [mission](missions/contract-and-implementation-harness.md). (R2/R3, glossary.)
- [ ] **Catalog / manifest + request-ledger.** The derived projection + the one new datum
  (who-requested). *Being instantiated now* per resolution 0003 (flat files); evaluate in use. (R5.)
- [ ] **Remaining architectural rules: layer-DAG + no-`dict[str,Any]`.** The core trio (body-dup,
  private-name-collision, dep-upper-bound) is **built native** (resolution 0005, `tools/arch_rules.py`).
  Still un-ported from a2kit: the import layer-DAG and the `dict[str,Any]`-ban. Add as fitness tests
  when a real layering/typing violation appears (do not build on spec). (R9.)

## Decide — open forks (a decision, not a build)

- [ ] **release-please** adoption timing. **Trigger:** the *first* tag/changelog bookkeeping mistake, OR
  a 2nd human contributor. Until then manual `git tag` at n=4 packages is fine. (R§6.5.)
- [ ] **Branding** — parked on purpose (user: dislikes both "shelf" and "microsoftware"; rename later).
  A separate pass, no throwaway names. (R11.)

## Parked — gated, do not touch yet

- **T0 primitives** (`atomic_io`, `duckdb_sidecar`, `managed_region`) — stay in a2kay at n=1; promote
  when a 2nd consumer pulls them (Article VII).
- **Onboarding runbook + `catalog`/`onboard` skill** — [mission](missions/onboarding-new-micro-software.md)
  captured; "do not build yet".

## Gaps

- [ ] **Guard enforcement is per-clone.** Onboarding installs the hook in one command
  (`tools/hooks/install.py`, §2), but git hooks can't be committed, so a fresh clone is unguarded until
  someone runs it. **Trigger:** a 2nd machine/clone, OR the first leaked override — then fold a
  working-tree check into `make check` (or enforce in CI).
