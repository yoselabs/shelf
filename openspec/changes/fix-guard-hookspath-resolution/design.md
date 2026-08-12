# Design

## The shape of the bug

```
                         installer's belief          git's actual lookup
                        ┌──────────────────┐        ┌────────────────────┐
  no core.hooksPath     │  .git/hooks/     │   ==   │  .git/hooks/       │   guard fires
                        └──────────────────┘        └────────────────────┘

                        ┌──────────────────┐        ┌────────────────────┐
  core.hooksPath set    │  .git/hooks/  ✔  │   !=   │  .beads/hooks/     │   guard DEAD
                        └──────────────────┘        └────────────────────┘
                            file exists,                git never looks
                          installer says ✔                   here
```

The two paths agreed for the guard's entire life, so nothing ever distinguished "wrote
the file" from "armed the hook". `core.hooksPath` splits them, and every signal the
operator has — the `✔`, the file on disk, `ls .git/hooks/` — reports on the left box.

## D1 — Resolve via `git rev-parse --git-path hooks`, not manual `core.hooksPath` reading

**Decision.** One call, not a conditional.

Rejected: `git config core.hooksPath` with a fallback to `git_dir / "hooks"`. It looks
equivalent and isn't — it re-implements git's own resolution (relative-path base,
`$GIT_DIR` interaction, worktree handling) and will drift from it. `--git-path` *is*
git's resolution, asked directly.

**Verified both branches** (2026-08-12):

| repo state | `git rev-parse --git-path hooks` |
|---|---|
| `core.hooksPath = /…/.beads/hooks` | `/Users/iorlas/Workspaces/shelf/.beads/hooks` |
| fresh `git init`, unset | `.git/hooks` |

Returns relative or absolute depending on the target, so `install.py`'s existing
normalization (`p if p.is_absolute() else repo / p`) still applies. Available since git
2.5 (2015) — below any plausible floor.

`_git_dir()` becomes unused by `main()` once this lands. Delete it rather than leave it
for a hypothetical caller (constitution: deletion is a virtue).

## D2 — Verify by executing the hook, not by inspecting it

**Decision.** After writing, prove the guard blocks. Assert on *behavior*, not on file
contents or mode bits.

This is the load-bearing decision. A content check (`MARKER in hook.read_text()`) or a
`+x` check would both have passed cheerfully throughout the entire period this repo was
unguarded — they inspect the left box. The only check that distinguishes the boxes is
running the thing git would run and observing a refusal.

The mechanism mirrors the probe that found the bug: seed an offending working state,
invoke the resolved hook as git invokes it, require a non-zero exit, restore. The
runbook already prescribes this shape for beads hooks (§2.2 step 3: "Run the hook
directly and confirm it reports pushing Dolt, **before** trusting a real `git push`").

Two constraints the implementation must honor, both discovered the hard way this session:

- **Restore state unconditionally.** The session that found this bug cleaned up its probe
  commit with `git reset --hard HEAD~1` and silently reverted unrelated tracked config
  (`.beads/config.yaml`), producing an hour of false diagnosis. Verification must not
  touch tracked state, and must not use `reset --hard` as cleanup. Prefer a temp file
  the guard rejects over anything that mutates the index or committed content.
- **A verification that cannot run is not a pass.** If the environment can't support it
  (guard script absent because the shelf isn't cloned — the `exit 0` branch in `HOOK`),
  report *unverified* distinctly from *verified*. Never let "couldn't check" print the
  same `✔` as "checked".

## D3 — Diagnose the foreign hook's owner; refuse; do not chain

**Decision.** Keep refusing, but name the manager and its real extension point.

The current message — "add this line to it" — was written for a hand-authored hook. With
`hooksPath` in play the file is almost always tool-generated, and hand-editing it is
advice that breaks on the owner's next regeneration. Detect by marker:

| marker found | correct extension point |
|---|---|
| `BEGIN BEADS INTEGRATION` | append **after** the `END` marker (adopt-beads §2.2 pattern) |
| husky | a new file under the husky hooks dir |
| lefthook | a `commands:` entry in `lefthook.yml` |
| pre-commit framework | `.pre-commit-config.yaml` (`no-local-shelf-source`, already shipped) |
| unrecognized | current generic advice, unchanged |

Rejected: auto-chaining. It converts a loud refusal into a silent time bomb — the append
survives until the owner regenerates, then vanishes without a word. Given this change
exists *because* a guard failed open silently, shipping a second silent-failure path in
the fix would be self-defeating. The refusal is correct behavior; only its diagnosis was
stale.

Note the pre-commit-framework row already works today and is verified (ledger 0038) —
that path sets `core.hooksPath` too, but the framework runs our hook itself, so the
guard was never dead there. Worth stating in the message so operators aren't sent
chasing a non-problem.

## D4 — What this deliberately does not fix

Existing clones stay unguarded until someone re-runs the installer. There is no
mechanism — and should not be one — for a repo to reach into another clone's git config.
The honest treatment is to say so in `consuming-the-shelf.md` and let `shelf-gag` add
the recurring check (`make check`-time liveness assertion) that makes an unguarded clone
*self-announcing* rather than silent. That ordering matters: this change makes the guard
verifiable, `shelf-gag` makes it continuously verified. Doing them together would blur
"the installer lied" with "nothing re-checks over time" — two different defects.

## Open question for implementation

Does the guard's own `exit 0` "shelf not cloned → do not block" branch (`HOOK`, line 28)
deserve the same scrutiny? It is a deliberate fail-open, and defensible — a consumer
without the shelf checked out shouldn't be unable to commit. But it is the same shape as
the bug being fixed: a guard that silently declines to guard. Not in scope here; worth a
bead if the answer isn't obviously "keep it".
