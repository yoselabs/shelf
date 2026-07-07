# shelf backlog

A **curated index**, not a source of truth — each item points at its authoritative home
(`R…` = a section of the exploration [thoughts doc](thoughts/2026-07-07-shelf-exploration.md);
`mission` / `resolution` = the track docs). **Prune, don't accumulate** (constitution III): when an
item is done, *delete its line* — the git history is the record. A growing backlog that no one prunes
is a smoke alarm.

## Verify — designed & shipped, never triggered end-to-end (highest risk)

- [ ] **Co-dev worktree loop, end-to-end.** Create `shelf-<project>` worktree → unstaged editable
  override in the consumer → edit a shelf pkg → see it live → revert → commit. The R1 ⚠ smoke-test in
  its final form. (`agent-loop.md` §6, `resolution 0001` known-open.)
- [ ] **Promote → tag → repoint → opt-in upgrade, for one real package.** The 4 packages were
  bootstrapped, not promoted through the loop; the cycle is theory until one package walks it.
  (`agent-loop.md` §4–5.)
- [ ] **Pre-commit-*framework* path.** The one-command installer (native hook) is tested and is the
  onboarding default; the `.pre-commit-hooks.yaml` `rev:` wiring (the framework alternative) has never
  been resolved by a real consumer.

## Build — designed, unbuilt, gated (do NOT build on spec)

- [ ] **Contract layer + `Implementation` build-vs-adopt harness (the crown insight).** No contract
  files exist. Deepest value; inert until a real 2nd consumer / contract need appears. **Home it as a
  mission** so it stops living only in the thoughts doc. (R2/R3, glossary.)
- [ ] **Catalog / manifest + request-ledger.** The derived projection + the one new datum
  (who-requested). Build when a 2nd consumer makes promotion real. (R5.)
- [ ] **Linter preset as shelf micro-software.** Only `tests/lib/boundary.py` exists; the a2lint-derived
  AST rules (AK200 layer-DAG · import discipline · AK214 no-`dict[str,Any]`) are un-reimplemented.
  Reimplement (do NOT depend on a2lint). (R9.)

## Decide — open forks (a decision, not a build)

- [ ] **Ontology fork:** model the ontology as a2kay EntityTypes vs flat manifest files. (R§6.3 —
  "worth one more explore pass".)
- [ ] **Linter preset shape:** config-preset vs CLI. (R§6.5.)
- [ ] **release-please** adoption timing — defer until release cadence hurts. (R§6.5.)
- [ ] **Branding** — deferred on purpose; a separate pass, no throwaway names. (R11.)

## Parked — gated, do not touch yet

- **T0 primitives** (`atomic_io`, `duckdb_sidecar`, `managed_region`) — stay in a2kay at n=1; promote
  when a 2nd consumer pulls them (Article VII).
- **Onboarding runbook + `catalog`/`onboard` skill** — [mission](missions/onboarding-new-micro-software.md)
  captured; "do not build yet".
- **LedgerEntry** (R154 fitness record) — later.

## Gaps

- [ ] **Guard enforcement is per-clone.** Onboarding now installs the hook in one command
  (`tools/hooks/install.py`, §2), but git hooks can't be committed, so a fresh clone is still unguarded
  until someone runs it. Durable backstop: enforce in CI or fold a working-tree check into `make check`.
  (Decide when a 2nd consumer/machine appears.)
