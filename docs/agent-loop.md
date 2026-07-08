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

## 2. ADOPT — before you hand-roll substrate

**Trigger:** you are about to write a helper, wrapper, adapter, or any substrate glue (LLM / DB /
embedding / git / file / format / config).

1. **Look first:** scan `<shelf>/docs/glossary.md` + `<shelf>/packages/`.
2. **Adopt only if it WINS the three-gate:** **DEEP** (hides real complexity, not a restatement) ·
   **STABLE** (settled API) · **WINS** (lighter than what you'd write). Any gate fails → **duplicate
   locally**. Duplication beats the wrong abstraction.
3. **Adopt =** add the git+tag source (`consuming-the-shelf.md` §1), `uv lock`, import. **Never** a
   committed local path.

## 3. PRODUCE — nominate vs promote (you may decide this yourself)

You are trusted to *notice* when substrate should become micro-software. But there are **two distinct
acts** with different bars — this split is what lets many parallel agents act freely without flooding
the shelf with half-baked packages:

- **Nominate — cheap, and self-consolidating.** You wrote substrate that smells reusable. Record it
  where your repo tracks reuse candidates (a2kay: `docs/design/primitive-shelf.md`, a rule-of-three
  *sighting count*). **Increment an existing entry if the pattern is already listed; add one only if
  genuinely new; delete an entry once it is promoted or abandoned.** This is not an append log — you
  prune it as you go, so it never becomes a pile someone must reconcile later. No package is created.
- **Promote — gated.** Turn a candidate into a real package + tag **only** when a **second** consumer
  actually wants it (Article VII, rule-of-three). One consumer is n=1 → nominate, don't promote.
  *Promotion, not publication.*

## 4. PROMOTE — the procedure (only when the gate is met)

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
