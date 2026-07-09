# The shelf loop — the standing instruction every consumer's agent self-applies

This is the **canonical loop**. A consumer's `AGENTS.md`/`CLAUDE.md` carries only a tiny *resolver*
block (see `consuming-the-shelf.md`); that block sends the agent here. **Read this once per session,
lazily, and cache it** — you are not expected to re-read or re-fetch it every action. It matures here,
in one place; every consumer picks up a new version the next time it `git pull`s the shelf.

The whole design is **structure over discipline**: the rules below are enforced by git and a commit
guard, not by an agent remembering to be careful. Many agent sessions run in parallel across many
consumer repos — none of them can corrupt the shelf or a consumer by forgetting a step.

**Leave it smaller.** Every time you build, remove dead code and collapse duplication — do not
accumulate. Append-only discipline applies *only* to parallel-safe coordination surfaces (constitution
III), never to the code itself; a growing file no one prunes is a smoke alarm, not progress.

**One shelf, per-project worktrees.** There is one shelf clone at the conventional path
(`$SHELF_HOME` → `~/Workspaces/shelf`). You **never edit the shelf in that main checkout.** Each
consuming project gets its own shelf **worktree named after the project's GitHub repo**:

```
git -C <shelf> worktree add ../shelf-<project> -b work/<project>   # isolated dir, shared objects
```

All shelf edits (promote, co-dev) for that project happen in `../shelf-<project>`. Two projects working
the shelf at once are on different worktrees + branches → they cannot collide. `git worktree remove`
it when the work has merged. **Reading** the shelf (this file, the catalog, the glossary) never needs a
worktree — the shared clone is enough; a worktree is only for *writing*.

Below: one `WORKFLOW` per situation. Match your situation to a `TRIGGER:`, run its `STEPS:`, expect
its `OUTPUT:`.

---

## WORKFLOW: SESSION-RESOLVE

TRIGGER: session start, or your cached shelf pull may be stale.

STEPS:
1. Find the local clone: `$SHELF_HOME` → `../shelf` → `~/Workspaces/shelf`.
2. Absent (greenfield)? `git clone https://github.com/yoselabs/shelf ~/Workspaces/shelf` — once.
3. Do **not** fetch just to start a session or write code — the clone on disk is enough to read
   this loop and the glossary.
4. First real checkpoint this session (about to enter `SEAM` or `PROMOTE`)? Pull once, lazily:
   `git -C <shelf> pull --ff-only`. Refreshes packages, tags, and this loop in one call.
5. **Staleness bound:** cached pull older than **1 hour**? Re-pull before entering `SEAM` or
   `PROMOTE` again, even mid-session — do not rely on "once per session" alone for long-running
   sessions. (Cheaper freshness peek, no working-tree change: `git -C <shelf> fetch --tags -q`.)

OUTPUT: a current local clone; this file and the catalog are guaranteed fresh for the next checkpoint.

---

## WORKFLOW: SEAM — the four directions

TRIGGER: you are about to write a helper, wrapper, adapter, or any substrate glue — LLM / DB /
embedding / git / file / format / config / datetime / collections / a wrapper over an awkward
stdlib or third-party API.

STEPS:
1. Compare against the **CATALOG** (`<shelf>/catalog/README.md` + `<shelf>/packages/` +
   `glossary.md`) — never against another consumer; you cannot see what else is being built, so
   the catalog is the frame.
2. Pick one direction:
   - **ADOPT** — a piece fits as-is: **DEEP** (hides real complexity) · **STABLE** (settled API) ·
     **WINS** (lighter than you'd write). Add the git+tag source (`consuming-the-shelf.md` §1),
     `uv lock`, import. **Never** a committed local path.
   - **EVOLVE** — a piece *almost* fits but isn't flexible enough → grow its contract to serve both
     cases (`PROMOTE` workflow, on the existing package), then adopt. One evolving piece beats two
     near-identical ones — *when the generalization stays coherent* (the `convert-md → convert_html`
     move). **When the candidate is a richer superset of a package that already exists, evolve to
     the superset — do not grow a sibling and promise to merge later** (resolution 0007, the
     monotonicity test): decide each axis by whether the new shape **exposes more and removes
     nothing** (rich return over bare value; fail-loud over errors-as-values — raising *surfaces*
     the failure). If it does → converge everyone onto it; the thin caller ignores the extra. Keep
     a narrower contract **only** where a consumer has a *stated, specific requirement* for it —
     otherwise a second contract is just quirk. A breaking evolution of an `active` package ships
     as a new tag with a migration note (see `PROMOTE` step 6); the old tag stays (opt-in upgrade).
   - **PROMOTE** — nothing covers it and it's generic → capitalize it now. The cheap moment; once
     it's wired into your app the chance is lost. Default posture: **promote, not defer** — a
     self-assessed "this feels reusable" is enough. Two guards only: **extracted** (real code your
     app needs, never an empty package) and **generic** (substrate, not your app's business logic /
     product moat). Genuinely unsure it's generic? Jot a one-line sighting where your repo tracks
     candidates and move on — the exception, not the main path. Do **not** hand-roll silently and
     move on — that's the extraction moment lost; over-promotion is cheap to fix at `RECONCILE`, a
     lost moment is not. → run `PROMOTE`.
   - **DUPLICATE / SKIP** — evolving would distort the piece (serve two masters badly), or your need
     is too niche → write it locally, don't force reuse. Revisited at `RECONCILE`.

OUTPUT: one of ADOPT (dependency added) / EVOLVE+ADOPT (via `PROMOTE`) / PROMOTE (via `PROMOTE`) /
DUPLICATE (local code, no shelf change).

---

## WORKFLOW: PROMOTE — extract or evolve generic substrate

TRIGGER: `SEAM` selected PROMOTE or EVOLVE.

STEPS:
1. **Worktree freshness first, before touching any file:** in `../shelf-<project>` (create it per
   "One shelf, per-project worktrees" above if absent), run `git fetch && git rebase origin/main`
   (or `pull --ff-only` if the branch has no local commits yet). Worktrees share git objects but
   **not** branch position — a worktree opened days ago can silently be behind `main`.
2. On branch `work/<project>` (create if absent).
3. Extract the code into `packages/<name>/` behind a stable **Capability**, with:
   - the **boundary test** — must not import any consumer app (the one invariant);
   - a **Contract** born `candidate` (inert until a live consumer breaks without it);
   - the package `pyproject.toml`.
4. `make check` green **in the worktree**.
5. Tag namespaced and push: `git tag <name>-vX.Y.Z && git push origin work/<project> --tags`.
   **Never delete an old tag** — that is what makes every consumer's upgrade opt-in.
6. **Repoint the origin consumer:** add the git+tag source, delete the in-repo copy, keep tests green.
7. **Breaking change?** Ship its migration in the same change, in two places:
   - a prose migration note where the change is announced (README, commit message);
   - a terse, arrow-notation entry in `packages/<name>/CHANGELOG.md` — one line per contract-shape
     change (old call/return/failure shape ⇒ new), **no prose, no rationale** (that's the ledger's
     job). AI-facing only: it exists so `RECEIVE` can answer "what do I change" without reading
     source. Example: `LLMAdapter.complete(prompt) -> str  ⇒  LLMProvider.complete(*, user, ...) -> Completion`.
     Only gets an entry on contract-shape changes — most releases add zero lines.
8. `git -C <shelf> worktree remove ../shelf-<project>` when the work has merged.

Push rejected (non-fast-forward, another session got there first)? `pull --rebase`, resolve, retry —
one-concept-per-file keeps textual conflicts rare by construction.

OUTPUT: a tagged, catalog-listed package; the origin consumer repointed at it; a `CHANGELOG.md`
entry if the change was breaking.

---

## WORKFLOW: RECEIVE — opt-in upgrades

TRIGGER: at your `SESSION-RESOLVE` checkpoint pull, a piece you pin has a newer tag.

STEPS:
1. Surface the newer tag; upgrading is never forced (old tags are never deleted — a shelf change
   can never silently break you).
2. Decide to upgrade? **Read `packages/<name>/CHANGELOG.md` first** — before source, before the
   README — for the exact contract-shape deltas.
3. Point the pin at the newer tag, `uv lock`.
4. **Migrate to the new idiom, not the smallest diff.** Rename call sites to match the new
   convention fully; delete compat shims. Don't wrap the new shape back into the old one at your
   boundary just to avoid touching call sites — that reintroduces the exact quirk the evolution
   removed.
5. Tests green.

OUTPUT: pin upgraded, call sites idiomatic to the new contract, nothing straddling both shapes.

---

## WORKFLOW: RECONCILE — the other half of aggressive promotion

TRIGGER: a deliberate, recurring pass (invoke it, or run during an onboarding catch-up) — not
per-feature work.

STEPS: walk `<shelf>/catalog/README.md`, ask per piece:
1. **Overlap?** Two packages doing almost the same thing → **merge** (lineage `merged-with` /
   `absorbed-into`).
2. **Kitchen-sink?** One package accreted unrelated concerns → **split** into coherent pieces.
3. **Unused?** No active use-case past its TTL → **deprecate → delete** (decay is a virtue).
4. **Over-promoted?** Turned out too niche / wrong shape → **demote**: duplicate back into its one
   consumer, retire the package. Expected and cheap to undo here — that's the deal.

Never delete a *tag* (`PROMOTE` step 5); retiring a package means marking it `deprecated` and
stopping new adoption.

OUTPUT: catalog garbage-collected with hindsight — "was that the right abstraction?" answered
empirically, not by an upfront gate.

---

## WORKFLOW: ESCAPE-HATCH — live co-development

TRIGGER: you must live-edit a shelf package and exercise it inside a consumer in the same loop.
Rare, structurally guarded.

STEPS:
1. Point the consumer's source at your project's shelf worktree
   (`../shelf-<project>/packages/<name>`).
2. **Keep that `pyproject.toml` change unstaged** — `git add` everything *except* `pyproject.toml`.
   uv reads the working-tree file, so co-dev stays live; other commits carry the committed git+tag
   pin and sail through.
3. Flip back to a tag only when you actually want to commit the dependency change itself.

The guard is per-repo, **staged-only**: it inspects *this repo's* staged `pyproject.toml` and
rejects a local `path=`/editable shelf source there. Never touches another repo, never blocks a
push, never forces reverting unrelated work — a wall exactly where you want one, the moment you try
to *commit* the override.

OUTPUT: live co-development without ever risking a committed local-path source.

---

## WORKFLOW: EVOLVE-THE-LOOP — updating this file

TRIGGER: friction with this loop discovered mid-session — a gap, an unclear rule, a judgment call
not covered.

STEPS:
1. Trivial / mechanical (typo, missing cross-link, obvious omission)? → fix this file directly. Done.
2. Otherwise: write a resolution (`docs/resolutions/000N-*.md`) — the fork rejected, the reasoning,
   an `Expires:` date.
3. **In the same change:** distill the operational takeaway into the relevant `WORKFLOW` block
   above. Fill the resolution's `Distilled into:` field with the workflow name, OR
   `N/A — self-enforcing via <test/tool>` if the resolution doesn't change agent behavior at all.
4. Never split steps 2–3 across changes. A resolution merged without its distillation is
   incomplete, not "to be done later" — `make check` enforces the field is filled (see
   `tests/test_resolution_distillation.py`), but only a human/agent discipline enforces that the
   *distillation itself* actually happened, so treat step 3 as non-optional.

OUTPUT: this file and its authoring resolution land in the same commit — the loop never silently
falls behind its own decisions.

---

## What is NOT in this loop

The **whole-codebase adoption sweep** — auditing an entire app for micro-software candidates and
researching which shelf pieces to adopt / promote / modernize so multiple consumers shrink — is a
separate, **deliberately-invoked** operation. Do not start it mid-feature. The procedure is
`docs/runbooks/onboard-a-consumer.md`.
