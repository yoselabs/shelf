---
id: 0009
title: Close the loop on every mutating workflow
statement: PROMOTE, RECEIVE and RECONCILE are done only when catalog, ledger and the main branch agree: just catalog, a ledger row per event, just check green, merged and pushed, worktree removed.
concerns: [workflow]
status: accepted
decided_by: owner
updated: 2026-07-09
expires: 2027-01-09
distilled_into: agent-loop.md `WORKFLOW: PROMOTE` step 8 (new); `WORKFLOW: RECEIVE` step 6 (new); `WORKFLOW: RECONCILE` closing step (new)
---

# 0009 — Every shelf-mutating workflow ends with a close-out, not just a merge

## Decision

A shelf-mutating workflow (`PROMOTE`, `RECEIVE`, `RECONCILE`) is not done when the code is correct;
it is done when the shelf's shared coordination surfaces agree with it and `main` carries it. Before
calling one finished:

1. `just catalog`: if `catalog/*.toml` or `use-cases/*.toml` changed, regenerate the derived
   `README.md`s in the same commit (a stale derived index looks authoritative and lies).
2. **A ledger entry** `ledger/00NN-<slug>.toml` using the *existing* event vocabulary (`delivery`,
   `verdict`, `verification`; grep `^event` before inventing one). A promotion is a `delivery` row, a
   consumer repoint (`RECEIVE`) a separate `verdict` row (`kept`/`adopted`/`rejected`), a `RECONCILE`
   action (merge/split/delete/demote) a `verdict` row against the affected packages. **Two events,
   two rows**; never collapse delivery+verdict into one row with a bolted-on field.
3. **Prune the backlog**: delete the line (`docs/backlog.md`) that triggered the work, or edit it to
   what remains. Since 2026-08-12 the backlog is beads (that file was deleted): close the bead.
4. `just check` green, **then merge the work branch into `main` and push**, not merely "in the
   worktree". A promotion that never reaches `main` never happened from any other session's view.
5. Only then `git worktree remove`, and delete the remote work branch if it merged cleanly.

**`RECEIVE` writes to the shelf too**, though it runs in a consumer's repo: the ledger write is a
shelf edit, so touch `../shelf-<project>` (create it if missing), append the `verdict` row,
`just catalog` if warranted, commit, push. Small, append-only, low-conflict, but via the worktree,
never a stray edit against the shared clone.

Propagated: `PROMOTE` step 8 "Close the loop" (the list above), `RECEIVE` step 6 (ledger `verdict`
row), `RECONCILE` closing step (`just catalog`, a `verdict` row per action, `just check`, merge+push).

## Rejected

- **Leaving it to inference.** The first end-to-end `PROMOTE` (2026-07-09, `atomic-io` /
  `duckdb-sidecar` / `managed-region`, ledger 0039/0040) worked mechanically but `agent-loop.md` had
  no step for catalog regeneration, ledger rows (the entry was inferred wrong: delivery+verdict
  collapsed into one row), merging to main (three ad hoc confirmations in one session), pruning the
  backlog, or naming the terminal state "tree clean, `main` pushed, no dangling worktree/branch".
  `RECEIVE` and `RECONCILE` had the same silence.
- **A fitness test now.** The next escalation, if drift recurs, is a `just check` test failing when
  `catalog/*.toml` changed in a diff with no matching `ledger/*.toml`. Deferred, not built: fix the
  known instance, do not pre-build enforcement for a violation that has not recurred.

## Risk, accepted

Adds ceremony to three workflows, against "structure over discipline". Accepted because the
alternative, proven that day, is an agent re-deriving or missing the same five facts every time with
no test to catch it (a discipline gap, not yet a structural one).

## History

- 2026-07-09: decided. Trigger: the first real end-to-end `PROMOTE`. Expires 2027-01-09 (re-justify
  once the close-out has been exercised enough to check it held). Track: governance / the promotion
  model.
