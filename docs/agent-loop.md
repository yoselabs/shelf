# The shelf loop — the standing instruction every consumer's agent self-applies

This is the **canonical loop**. A consumer's `AGENTS.md`/`CLAUDE.md` carries only a tiny *resolver*
block (see `consuming-the-shelf.md`); that block sends the agent here. **Read this once per session,
lazily, and cache it** — you are not expected to re-read or re-fetch it every action. It matures here,
in one place; every consumer picks up a new version the next time it `git pull`s the shelf.

The whole design is **structure over discipline**: the rules below are enforced by git and a commit
guard, not by an agent remembering to be careful. Many agent sessions run in parallel across many
consumer repos — none of them can corrupt the shelf or a consumer by forgetting a step.

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

- **Nominate — cheap, do it freely.** You wrote substrate that smells reusable. Record it: append a
  one-line candidate note where your repo tracks candidates (a2kay: `docs/design/primitive-shelf.md`, a
  rule-of-three sighting count; if your repo has no such ledger, append to `docs/shelf-candidates.md`).
  **Append-only → conflict-free across parallel sessions.** No package is created.
- **Promote — gated.** Turn a candidate into a real package + tag **only** when a **second** consumer
  actually wants it (Article VII, rule-of-three). One consumer is n=1 → nominate, don't promote.
  *Promotion, not publication.*

## 4. PROMOTE — the procedure (only when the gate is met)

Isolate on a **worktree** so concurrent promotions never collide on the shared clone:

1. `git -C <shelf> worktree add ../shelf-<name> -b promote-<name>` — isolated working dir, shared objects.
2. Extract the code into `packages/<name>/` behind a stable **Capability**, with:
   - the **boundary test** — the piece must not import any consumer app (the one invariant);
   - a **Contract** born `candidate` (inert until a live consumer breaks without it);
   - the package `pyproject.toml`.
3. `make check` green **in the worktree**.
4. Tag namespaced and push: `git tag <name>-vX.Y.Z && git push origin promote-<name> --tags`.
   **Never delete an old tag** — that is what makes every consumer's upgrade opt-in.
5. **Repoint the origin consumer:** add the git+tag source, delete the in-repo copy, keep its tests green.
6. A **breaking change ships its migration in the same change**.
7. `git -C <shelf> worktree remove ../shelf-<name>` when merged.

Push rejected (non-fast-forward, another session got there first)? `pull --rebase`, resolve, retry —
append-only + one-concept-per-file make textual conflicts rare by construction.

## 5. RECEIVE updates — opt-in, never forced

At your lazy checkpoint pull, if a piece you pin has a **newer tag**, surface it and consider upgrading.
Upgrade = point at the newer tag + `uv lock`. Because old tags are never deleted, **a shelf change can
never silently break you** — every upgrade is a deliberate choice.

## 6. The editable escape hatch — rare, structurally guarded

Only when you must live-edit a shelf package and exercise it inside a consumer in the same loop:

- Override the source to a local path (or a `git worktree` checkout) that is **uncommitted**. Revert to
  the git+tag pin **before** committing.
- You **physically cannot commit it**: the shelf's pre-commit guard (installed per
  `consuming-the-shelf.md` §2) rejects any commit carrying a local `path=` / editable shelf source. This
  is a wall, not a convention — so no parallel session can poison a consumer by forgetting to revert.

## 7. What is NOT in this loop

The **whole-codebase adoption sweep** — auditing an entire app for micro-software candidates and
researching which shelf pieces to adopt or modernize — is a separate, **deliberately-invoked** operation.
Do not start it mid-feature. See `docs/missions/onboarding-new-micro-software.md`.
