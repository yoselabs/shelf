---
id: 0030
title: Tolerance and destructive flags are debt, converted to exceptions and verbs
statement: force, missing_ok, ignore_errors, overwrite and kin are not a justified exception; the call raises a typed exception and the caller that tolerates it catches it.
concerns: [doctrine]
status: accepted
decided_by: owner
updated: 2026-11-21
distilled_into: N/A — self-enforcing via tests/test_arch_bool_modes.py
---

# 0030 — Tolerance and destructive flags are debt, converted to exceptions and verbs

## Decision

The first version of this ADR (2026-11-20) allowed a destructive or tolerant bool as a named `exception:` row
(`force`, `allow_delete`, `missing_ok`, `clean(ignored=, nested=)`, `record(allow_empty=, hooks=)`,
`park(keep_ignored=)`, `unclaim(force=)`, `reclaim(any_replica=)`). The owner reversed it the same day: those rows
were debt, and they are converted (shelf-tyld.26). Article III now says it: **tolerance is a handler, not a flag.**

- **No flag chooses how a call tolerates failure or how destructive it is.** `missing_ok=`, `ignore_errors=`, `force=`,
  `overwrite=`, `exist_ok=`, `check=` and kin are not public parameters. The call raises a typed exception; the caller
  that tolerates it catches that exception (`NotAWorktree`, `GitUnavailable`). A tiny typed exception class is added
  per package where none fits.
- **Two actions that differ in kind are two verbs** (`drop_worktree` / `discard_worktree`, `unclaim` / `evict`,
  `record` / `record_with_hooks` / `record_empty`), or ONE idempotent verb when that is the honest meaning
  (`abort_rebase` with nothing paused only restores). The smaller API wins: every public name costs tokens.
- **A dangerous form is refused, not confirmed.** `push_refspecs` / `push_request` raise `PushRefused` for `+`, `:dst`,
  `--force`, `--delete`, `--mirror`, `--prune`; a caller who really needs one gets one named verb (`delete_remote_at`,
  `push_lease`), never a flag. A `force=True` beside `"+main"` only repeated the form.
- **A `Literal` or enum parameter is the same flag in a coat** and is not the answer.
- **What stays as a flag** (rows in `tests/test_arch_bool_modes.py`, each with a reason that names its class):
  - `cost:` the default is the complete or durable answer and the flag skips or adds one named cost (Article IX):
    `fsync=False`, `worktrees(with_dirty=)`, `readiness(check_push=)`, the runner's `pin=False`.
  - `construction:` chosen once when the object is built, never per call (`memoize`).
  - `fact:` data about one value or error, or a third-party library's own option (`retryable`, `include_links`).
- **Enforced** by `tests/test_arch_bool_modes.py`: bool-with-default parameters (as before), and a second check on every
  public parameter named `force`, `overwrite`, `missing_ok`, `exist_ok`, `ignore_errors` or `check`, or annotated
  `Literal` or an Enum (aliases included). `debt:` rows in that check are the remaining `Literal` switches
  (`record(mode=)`, `finish_rebase(action=)`, `rebase_onto(squash_failure=)`, `take_branch(mode=)`, any-markdown
  `anchors`, page-tsv `consumer`, blueprint `scan(mode=)`); each is a conversion still owed, not precedent.

Why: a flag that makes a failure acceptable hides a second mode in one signature, and a caller reading
`drop_worktree(p, missing_ok=True)` cannot see which failures are swallowed. An exception names the failure, the
`except` names the caller's choice, and `grep NotAWorktree` finds every place that tolerates it.

## Rejected

- Keep the destructive flags as a justified exception mirroring the tool's own flag (the first version): the flag is the
  hidden second mode Article III forbids, and `git push --force` as a word is not a reason to copy it into every
  signature.
- A `Literal` policy parameter (`on_missing="ignore" | "raise"`): the same flag in a coat.
- Keep a guard flag that confirms the dangerous form (`force=True` beside `"+main"`), or send the form as written: the
  first is ceremony, the second drops the pit of success.
- Convert the cost opt-ins too: separate `*_nofsync` functions would double atomic-io's surface for a named cost;
  they stay rows until a second cost class shows up.

## History

- 2026-11-20: first version, "a destructive opt-in bool is a justified exception" (shelf-tyld.13).
- 2026-11-21: reversed and rewritten: these flags are debt; 20 rows converted (shelf-tyld.26).
