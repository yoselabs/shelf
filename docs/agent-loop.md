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
it when the work has merged.

## 1. Fetch cadence — protect tokens

- **Do NOT fetch to start a session or to write code.** The shelf clone on disk is enough to read this
  loop and the glossary.
- **Fetch/pull ONCE, lazily**, at your first real checkpoint (about to adopt or promote), then cache
  for the session: `git -C <shelf> pull --ff-only`. That single call refreshes the packages, the tags,
  **and** this loop.
- Cheaper freshness peek (no working-tree change): `git -C <shelf> fetch --tags -q`. One call, cached.

## 2. At a seam — the four directions (before you hand-roll substrate)

**Trigger:** you are about to write a helper, wrapper, adapter, or any substrate glue — LLM / DB /
embedding / git / file / format / config / datetime / collections / a wrapper over an awkward stdlib
or third-party API.

**Compare against the CATALOG** (`<shelf>/catalog/README.md` + `<shelf>/packages/` + `glossary.md`) —
**never** against another consumer; you cannot see what else is being built, so the catalog is the frame.
Then take **one of four directions**:

1. **ADOPT** — a piece fits as-is: **DEEP** (hides real complexity) · **STABLE** (settled API) · **WINS**
   (lighter than you'd write). Add the git+tag source (`consuming-the-shelf.md` §1), `uv lock`, import.
   **Never** a committed local path.
2. **EVOLVE** — a piece *almost* fits but is not flexible enough → **grow its contract to serve both
   cases** (§4, on the existing package: add the capability + tests, cut a new tag), then adopt it. One
   evolving piece beats two near-identical ones — *when the generalization stays coherent*. This is the
   `convert-md → convert_html` move.
3. **PROMOTE** — nothing covers it and it is generic → capitalize it now (§3). The cheap moment; once it
   is wired into your app the chance is lost.
4. **DUPLICATE / SKIP** — evolving would distort the piece (serve two masters badly), or your need is too
   niche → write it locally, don't force reuse. The call is revisited at reconciliation (§5b).

## 3. PRODUCE — promote aggressively, at writing time (resolution 0006)

You are trusted to *notice* when substrate should become micro-software, and to **promote it in the
moment** — no second consumer required. The default for anything generic is **promote**, not defer:

- **Promote — the cheap default for generic substrate.** You are writing a helper, a pattern + its
  safety wrapper, a datetime/collection util, or an abstraction over an awkward API — and it smells
  reusable. Promote it to the shelf now (§4). A self-assessed "this feels reusable" is enough. The bar
  is only the two guards: it is **extracted** (real code your app needs, never an empty package), and it
  is **generic** (substrate, not your app's business logic / product moat).
- **Nominate — only when you're genuinely unsure it's generic.** Borderline? Jot a one-line sighting
  where your repo tracks candidates (a2kay: `docs/design/primitive-shelf.md`) and move on; prune it when
  resolved. This is now the *exception*, not the main path — do not hoard candidates you could promote.
- **Do NOT hand-roll silently.** The one thing to avoid is writing generic substrate inline and moving
  on — that is the extraction moment lost. Over-promotion is cheap to fix at reconciliation (§5b);
  a lost moment is not.

## 4. PROMOTE — the procedure (whenever you extract generic substrate)

Work in **your project's shelf worktree** (`../shelf-<project>`, see "One shelf, per-project worktrees"
above) so concurrent promotions from different projects never collide:

1. In `../shelf-<project>` on branch `work/<project>` (create it if absent).
2. Extract the code into `packages/<name>/` behind a stable **Capability**, with:
   - the **boundary test** — the piece must not import any consumer app (the one invariant);
   - a **Contract** born `candidate` (inert until a live consumer breaks without it);
   - the package `pyproject.toml`.
3. `make check` green **in the worktree**.
4. Tag namespaced and push: `git tag <name>-vX.Y.Z && git push origin work/<project> --tags`.
   **Never delete an old tag** — that is what makes every consumer's upgrade opt-in.
5. **Repoint the origin consumer:** add the git+tag source, delete the in-repo copy, keep its tests green.
6. A **breaking change ships its migration in the same change**.
7. `git -C <shelf> worktree remove ../shelf-<project>` when the work has merged.

Push rejected (non-fast-forward, another session got there first)? `pull --rebase`, resolve, retry —
one-concept-per-file keeps textual conflicts rare by construction.

## 5. RECEIVE updates — opt-in, never forced

At your lazy checkpoint pull, if a piece you pin has a **newer tag**, surface it and consider upgrading.
Upgrade = point at the newer tag + `uv lock`. Because old tags are never deleted, **a shelf change can
never silently break you** — every upgrade is a deliberate choice.

## 5b. RECONCILE — the other half of aggressive promotion (Article VIII, resolution 0006)

Aggressive promotion (§3) is only healthy if the catalog is **garbage-collected with hindsight**. This is
not per-feature work; it is a deliberate, recurring pass (invoke it, or run it during an onboarding
catch-up). Walk `<shelf>/catalog/README.md` and ask, per piece:

- **Overlap?** Two packages doing almost the same thing → **merge** (lineage `merged-with` / `absorbed-into`).
- **Kitchen-sink?** One package accreted unrelated concerns → **split** into coherent pieces.
- **Unused?** No active use-case past its TTL → **deprecate → delete** (decay is a virtue).
- **Over-promoted?** Turned out too niche / the wrong shape → **demote**: duplicate it back into its one
  consumer and retire the package. Over-promotion is *expected* and cheap to undo here — that is the deal.

This is where "was that the right abstraction?" is finally answered — empirically, not by an upfront gate.
Never delete a *tag* (§4); retiring a package means marking it `deprecated` and stopping new adoption.

## 6. The editable escape hatch — rare, structurally guarded

Only when you must live-edit a shelf package and exercise it inside a consumer in the same loop:

- Point the consumer's source at your project's shelf worktree (`../shelf-<project>/packages/<name>`),
  and **keep that pyproject change unstaged** — `git add` everything *except* `pyproject.toml`. uv reads
  the working-tree file, so co-dev stays live; your other commits carry the committed git+tag pin and
  sail through. Flip back to a tag only when you actually want to commit the dependency change itself.
- The guard is per-repo and **staged-only**: it inspects *this repo's* staged `pyproject.toml` and
  rejects a local `path=`/editable shelf source there. It never touches another repo, never blocks a
  push, and never forces you to revert to commit unrelated work — so it cannot disturb a parallel
  session in another project (different file, different hook). It is a wall exactly where you want one:
  the moment you try to *commit* the override.

## 7. What is NOT in this loop

The **whole-codebase adoption sweep** — auditing an entire app for micro-software candidates and
researching which shelf pieces to adopt / promote / modernize so multiple consumers shrink — is a
separate, **deliberately-invoked** operation. Do not start it mid-feature. The procedure is
`docs/runbooks/onboard-a-consumer.md`.
