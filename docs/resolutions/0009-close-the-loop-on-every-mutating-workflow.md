# 0009 — Every shelf-mutating workflow ends with a close-out, not just a merge

- **Status:** decided (2026-07-09)
- **Expires:** 2027-01-09 (re-justify once the close-out step has been exercised enough times to check whether it held)
- **Track:** governance / the promotion model
- **Distilled into:** agent-loop.md `WORKFLOW: PROMOTE` step 8 (new); `WORKFLOW: RECEIVE` step 6 (new);
  `WORKFLOW: RECONCILE` closing step (new)

## The fork

2026-07-09 was the first time `PROMOTE` ran end-to-end on a real package (`atomic-io` /
`duckdb-sidecar` / `managed-region`, a2kay's T0 primitives — ledger 0039/0040) instead of being
bootstrapped. The mechanical steps (worktree, extract, name, boundary test, tag, push, repoint,
delete the origin copy) all worked cleanly. What didn't exist anywhere in `agent-loop.md`:

- **No step regenerates the catalog.** `PROMOTE` step 3 has you hand-write `catalog/*.toml` +
  `use-cases/*.toml`, but nothing says `make catalog`. Caught only because the *session* also knew
  `CLAUDE.md`'s `make check` target — a session that only reads `agent-loop.md` (as the file's own
  header prescribes: "read this once, lazily, cache it") would miss it.
- **No step writes a ledger entry.** `constitution.md` calls the ledger "the fitness record," but
  `PROMOTE`'s `STEPS`/`OUTPUT` never mention it. Written from inferred convention (39 prior rows),
  not a prescribed step — and inferred *wrong*: the entry collapsed the established `delivery` +
  `verdict` two-row pattern into one row with an invented `verdict` field on a `delivery` event,
  a schema drift only caught by grepping `event =` values across every existing row.
- **Merge-to-main is presupposed, never instructed.** `PROMOTE` step 8 (now 9) says "worktree
  remove... when the work has merged" — but no step 1–7 says *merge `work/<project>` into `main`,
  push*. This produced three separate ad hoc confirmations in one session (tag+push, push the
  consumer repo, push shelf `main` + delete the branch) instead of one named step to just execute.
- **No step prunes `docs/backlog.md`.** The file's own header says "prune, don't accumulate," but
  no `WORKFLOW` references closing the backlog line that triggered the work.
- **`RECEIVE` and `RECONCILE` have the identical silence** — no catalog/ledger/backlog step in
  either, despite the ledger's real rows showing every `RECEIVE`-shaped event (adopt/kept) logged
  as a `verdict` row, and every `RECONCILE`-shaped event (merge/split/delete/demote) being exactly
  the kind of catalog-mutating fact the ledger exists to record.
- **The loop's own terminal state is undefined.** Nothing names "working tree clean, `main` pushed,
  no dangling worktree/branch" as the checkable end state every workflow above converges on.

## The rule

**A shelf-mutating workflow (`PROMOTE`, `RECEIVE`, `RECONCILE`) is not done when the code change is
correct — it is done when the shelf's shared coordination surfaces agree with it and `main` carries
it.** Concretely, before calling any of these three workflows finished:

1. `make catalog` — if `catalog/*.toml` or `use-cases/*.toml` changed, the derived `README.md`s must
   be regenerated in the same commit. A stale derived index is worse than a missing one — it looks
   authoritative and lies.
2. **A ledger entry** — append `ledger/00NN-<slug>.toml` using the *existing* event vocabulary
   (`delivery`, `verdict`, `verification` — grep `ledger/*.toml` for `^event` before inventing a
   new one). `PROMOTE` landing a package is a `delivery` row; a consumer repointing (`RECEIVE`) is a
   separate `verdict` row (`kept`/`adopted`/`rejected`); a `RECONCILE` action (merge/split/delete/
   demote) is a `verdict` row against the affected package(s). **Two events, two rows** — collapsing
   delivery+verdict into one row with a bolted-on field is the exact drift this resolution responds
   to; don't repeat it.
3. **Prune `docs/backlog.md`** — if this workflow closed the line that triggered it, delete that
   line in the same change. If it only partially closes an item, edit the line to say what remains.
4. `make check` green, **then merge the work branch into `main` and push** — not merely "in the
   worktree." A promotion that never reaches `main` never happened, from any other session's point
   of view.
5. Only then: `git worktree remove`, and delete the remote work branch if it merged cleanly (a
   merged branch left behind is dead weight, not a safety net — the commit lives on in `main`).

**`RECEIVE` writes to the shelf too, even though it runs in a consumer's repo.** Ledger writes are a
shelf edit — per "One shelf, per-project worktrees," that means touching `../shelf-<project>`
(create it if this session doesn't have one yet), appending the `verdict` row, `make catalog` if
warranted, commit, push. This is a small, low-conflict, append-only write — it does not need the
full worktree ceremony `PROMOTE` does, but it does need the worktree, not a stray edit against the
shared clone.

## What changes (propagated)

- **`PROMOTE` step 8 (new, before the renumbered worktree-remove step):** "Close the loop" — the
  five-point list above, condensed to a step.
- **`RECEIVE` step 6 (new):** append the ledger `verdict` row in `../shelf-<project>`, per the
  paragraph above.
- **`RECONCILE`:** gains a closing step mirroring `PROMOTE` step 8 — `make catalog`, a `verdict` row
  per action taken, `make check`, merge + push.

## The risk, named

This adds ceremony to every one of these three workflows, and ceremony is exactly what "structure
over discipline" (this file's own opening line) is supposed to make unnecessary. Accepted because
the alternative — proven today — is an agent re-deriving the same five facts from scratch, or
missing one of them, every single time, with no test to catch it (there is no `test_ledger_entry_
exists.py`; this is a discipline gap, not yet a structural one). If this recurs after the
distillation, the next escalation is a `make check` fitness test that fails when `catalog/*.toml`
changed in a diff without a matching `ledger/*.toml` — deferred, not built now, because one
resolution should fix the *known* instance of drift, not pre-build enforcement for a violation that
hasn't recurred yet.
