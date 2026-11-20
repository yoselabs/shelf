---
id: 0030
title: A destructive opt-in bool is a justified exception
statement: A bool that opts one call into a destructive or history-changing act (force, allow_delete, ignored, nested, allow_empty, hooks, keep_ignored) is allowed when the safe act is the default.
concerns: [doctrine]
status: accepted
decided_by: owner
updated: 2026-11-20
distilled_into: N/A — self-enforcing via tests/test_arch_bool_modes.py
---

# 0030 — A destructive opt-in bool is a justified exception

## Decision

Article III bans optionality: a bool with a default that picks between two behaviours is split into two functions or
types. One class stays a flag, as a named `exception:` row in `tests/test_arch_bool_modes.py`:

- **The destructive opt-in.** The flag asks for the one act that loses data or history (`force`, `allow_delete`,
  `clean(ignored=, nested=)`, `record(allow_empty=, hooks=)`, `park(keep_ignored=)`, `unclaim(force=)`,
  `reclaim(any_replica=)`). It qualifies only when all hold:
  1. The default is the safe act. The caller types the flag to lose anything.
  2. The flag mirrors the tool's own flag (`git push --force`, `git clean -x`, `--allow-empty`, `--no-verify`,
     `bd --force`), so a reader meets the same word, not a second vocabulary.
  3. The call is otherwise the same: a second function would repeat the signature and drift from the first.
  4. The row names the flag and the call; the reason is in the allowlist, not "pre-existing".
- **Absence tolerance** (`missing_ok`): the caller names that a missing target is success, as `Path.unlink(missing_ok=)`
  does. Allowed for the same reason (named, same call). A split would need an outcome value on three result shapes.

- **Cost opt-in** (`fsync=False`, `worktrees(with_dirty=)`, `readiness(check_push=)`, the runner's `pin=False`): the
  default is the complete or durable answer and the flag skips or adds a named cost. **Construction config**
  (`memoize`, anyembed `gpu`): chosen once when the object is built, never per call.

A flag that fails a test (the default is the destructive act, or the call differs) is a split, not a row.

Why: a destructive act behind its own function name (`force_push`) is the same flag with more files, and every
consumer already knows `--force`. What Article III guards is a hidden second mode; a loud, named, default-off one is
the pit of success.

## Rejected

- Split every destructive flag into a `*_force` function: doubles the Repo protocol, its real and fake
  implementations and the contract suite for no safety the default does not already give.
- Return an outcome value instead of `missing_ok`: right in principle, deferred; reopen when a result type is next
  changed.
- Leave the rows unjustified: the allowlist would hold 24 rows nobody can challenge.

## History

- 2026-11-20: decided (shelf-tyld.13), from the 24 `exception:` rows of docs/bool-modes-triage.md.
