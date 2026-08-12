---
name: onboard-consumer
description: Onboard a project as a shelf (github.com/yoselabs/shelf) consumer — commit guard, resolver block, beads, and the python+uv linter preset — in one adaptive, verified pass. Use whenever the user wants to set up a new or existing repo to consume the shelf, add beads to a project alongside the shelf, or asks why onboarding keeps landing half-done (guard installed dead, resolver block out of date, bd config silently reverted). Not for adding a specific shelf package dependency (that's a separate DEEP·STABLE·WINS decision) or for the shelf repo's own development.
---

# Onboard a project as a shelf consumer

Wires a repo to consume the shelf and (by default) beads, then proves each piece actually works —
not just that a file landed. Read `<shelf>/openspec/changes/onboard-consumer-skill/design.md` (D1,
D4) if you want the full reasoning; the short version is below.

## The split this skill relies on

**You decide what this repo needs. You do not decide, or re-verify, whether a step worked.**

Five operations under `tools/onboard/` do the actual work — `guard`, `resolver-block`, `beads`,
`linter-preset`, and `verify`. Each is idempotent, checks its own preconditions, and asserts its
own effect by exercising it, never by checking that a file exists. Ordering is enforced by the
operations themselves (`beads` refuses to run before `guard` has verified — otherwise `bd init`
can seize `core.hooksPath` and leave the guard installed dead) — not by you calling them in the
right sequence. Re-running the whole thing on an already-onboarded repo is safe and is how you
check its current state.

Your job is judgment: what does *this* repo need, what already exists here, what should be
skipped. Never re-implement what the operations already guarantee, and never report a step as
verified based on your own inspection instead of the operation's own `Result`.

## Steps

1. **Find the shelf clone**: `$SHELF_HOME` → `../shelf` → `~/Workspaces/shelf`. If none exists,
   clone one (`git clone https://github.com/yoselabs/shelf ~/Workspaces/shelf`) — this is a normal
   part of onboarding, not an error.

2. **Look at the target repo before running anything.** You're deciding inputs, not outcomes:
   - **Greenfield or established?** An established repo may benefit from a separate catch-up sweep
     (checking for an existing shelf dependency worth adopting, existing lint config, etc.) — that
     is genuinely different work, out of scope here. Mention it, don't do it.
   - **Does it already have a hook manager?** You don't need to diagnose this yourself — the
     `guard` operation's underlying installer already detects beads/pre-commit/husky/lefthook and
     refuses to clobber a foreign hook, naming the tool and where to add to it instead. Just relay
     what it reports; don't re-derive the diagnosis or second-guess it.
   - **Is beads wanted?** Default yes — most shelf consumers use it. Ask if it's not obvious from
     context; `--no-beads` skips it and everything else still applies.
   - **Is this a python+uv project?** Auto-detected from `pyproject.toml`'s presence — you don't
     need to ask or inspect further.

3. **Run the operations**:

   ```bash
   python3 "$SHELF_HOME/.agents/skills/onboard-consumer/scripts/onboard.py" --repo /path/to/consumer
   # add --no-beads if beads isn't wanted
   ```

   This prints one line per operation: `<name>: <outcome> (verified=<bool>) — <message>`, and
   exits non-zero if anything did not fully succeed. The script carries no judgment of its own —
   it's steps 3 onward of the split above, mechanical by design.

4. **Report the per-operation results as printed** — outcome, `verified`, and message, one line
   each. Never collapse them into a single "onboarding succeeded/failed" without showing which
   operation is which; a `could_not_apply` (e.g. `linter-preset` on a non-python repo) is a
   distinct, expected outcome, not a failure to explain away. If an operation reports `failed` or
   `could_not_apply` unexpectedly, do not attempt to manually fix its target file — either fix the
   underlying operation (it's a real module in `tools/onboard/`, with tests) or report the blocker
   plainly. Papering over a bad `Result` by hand-editing the file it was supposed to produce
   defeats the entire point of the verification the operation just did.

## What this skill must never do

- **Add a shelf package dependency.** Onboarding wires the *mechanism* for consuming the shelf; it
  never adopts a specific package. That's a separate decision (DEEP · STABLE · WINS, see
  `docs/consuming-the-shelf.md` §1) made deliberately, never as a side effect of onboarding.
- **Re-order the operations "for efficiency."** The order the script uses already respects every
  known precondition (`beads` after `guard`). If you're calling operations directly instead of via
  the script, `run_all()` (`tools/onboard/operations.py`) enforces this regardless of the order you
  hand it — but there's no reason to bypass the script.
- **Trust a step because a file appeared.** Only the operation's own `Result.verified` counts.
