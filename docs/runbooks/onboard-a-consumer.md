# Runbook — onboard a full consumer + the whole-codebase adoption sweep

The **heavy, deliberately-invoked** operation (agent-loop.md §7): bring a project in as a shelf consumer
*and* audit its whole codebase for micro-software — what to **adopt**, what to **duplicate**, and what to
**promote** so that **multiple consumers shrink**. Distinct from the light standing loop; run it in a
dedicated session, not mid-feature.

The prize is not "this project uses the shelf." It is: **where two consumers hand-roll the same
substrate, promote one shared piece and delete it from both** — total code goes *down*.

---

## Phase A — mechanical onboarding (fast, mostly reversible)

From `consuming-the-shelf.md`, in the consumer repo root:

1. **Guard:** `python "$SHELF_HOME/tools/hooks/install.py"` (per-clone; blocks a committed editable shelf source).
2. **Resolver block:** paste the block from `consuming-the-shelf.md` §3 into the consumer's `AGENTS.md`/`CLAUDE.md`.
3. **Inherit the linter reference** (config-preset, resolution 0004): copy the `[tool.ruff|codespell|coverage]`
   blocks, the `Makefile` targets, and the `dev` group from the shelf; then own the copy. See `docs/linting.md`.
4. **Deps come later** — do NOT add shelf git+tag sources yet. You add one only when the sweep says *adopt*.

Onboarding ≠ adopting. A consumer can be fully onboarded and adopt zero packages if nothing passes the gate.

## Phase B — the substrate inventory (read-only)

Produce a table of every place the consumer hand-rolls substrate (not product). Method (the `micro-software`
K skill):

1. **Docstring census + coupling grep:** LLM / embedding / DB / git / HTTP / file-IO / format-conversion /
   config / retry / concurrency glue. For each: file, the *capability* it provides, and its API surface.
2. **Apply the stop-caring litmus:** would the app be simpler if it *stopped caring* which backend is under
   this? Yes → substrate (a candidate). No → product (leave it).
3. Record surface shape: is it Path-based? string-based? sync/async? what does it return (bare value vs a
   rich result with accounting)? — this is what decides fit later.

## Phase C — cross-reference (the multi-consumer core)

For each substrate candidate, check **three** places — this is where "satisfy both, reduce both" happens:

1. **The shelf catalog** (`<shelf>/catalog/README.md`): does a package already provide this Capability?
2. **The other consumers** (e.g. `~/Workspaces/a2kay`, `~/Workspaces/a2web`): do they hand-roll the *same*
   substrate? Use the arch engine cross-repo:
   `uv run python <shelf>/tools/arch_advisory.py` is intra-shelf; for cross-repo, run the same
   `arch_rules` fact extractor over both consumers' `src/` and look for shared body-hashes / helper names.
3. **The richer implementation wins the design.** If two consumers both have an abstraction and one is a
   *superset* (async, cost accounting, more backends), that superset — not the thinner one — is the promote
   candidate. (Live example: a2web's `llm_extract.Provider` is richer than `anyllm`; the arrow may **reverse**.)

## Phase D — the per-candidate verdict (DEEP · STABLE · WINS)

| Situation | Verdict | Action |
|---|---|---|
| Shelf already provides it **and** it passes DEEP·STABLE·WINS for *this* consumer's real surface | **ADOPT** | git+tag source, `uv lock`, delete the hand-roll, publish a `use-cases/<consumer>--<sw>.toml`, add a ledger `verdict` entry. |
| Shelf provides it but the **contract shape is wrong** (Path vs string, sync vs async, drops data the consumer needs) | **DON'T ADOPT** | Duplicate locally (constitution VI). Record a *field signal* in `<shelf>/docs/backlog.md` — the contract gap is a future evolution, not a today-build. |
| **Two+ consumers** hand-roll the same substrate and no shelf piece exists (or the shelf piece is a subset) | **PROMOTE** | Promote the *superset* to the shelf (Phase E), then both consumers adopt and delete their copies. This is the win. |
| One consumer only (n=1), reusable-smelling | **NOMINATE** | Record in the consumer's own reuse ledger (rule-of-three sighting). Do not promote (Article VII). |

Never adopt on hope. Duplication is cheaper than the wrong abstraction — the eval saying *don't adopt* is a
success, not a miss.

## Phase E — promote (only when Phase D says PROMOTE; the gate is met)

Follow **agent-loop.md §4** exactly, in the project's shelf worktree `../shelf-<project>`:
extract behind a Capability + boundary test + `candidate` Contract; `make check` green in the worktree;
tag namespaced; repoint **every** consumer that wants it (delete each in-repo copy, keep tests green); a
breaking change ships its migration. For a *superset* promotion that supersedes an existing thinner package,
the old package is `deprecated` (not deleted — Article VIII) with a migration note; consumers move opt-in.

## Phase F — record & report

- **Publish use-cases**: one `use-cases/<consumer>--<sw>.toml` per adopted piece (why + what — the retention claim).
- **Ledger**: append a `<seq>-<consumer>-<sw>-<event>.toml` per delivery/verdict; `make catalog`.
- **Adoption report**: a table of every candidate → verdict → action, plus the net line-count delta across
  all touched repos. If it did not make at least one codebase *smaller*, question whether the abstraction was real.

## Guardrails

- **Report before invasive change.** Phases B–D are read-only and produce the report; get human sign-off
  before deleting consumer code or cutting a promotion tag.
- **Cross-repo edits stay isolated:** consumer changes in the consumer repo; shelf changes in
  `../shelf-<project>`. Never edit the shelf main checkout.
- **`make check` green** in every repo you touch before you stop.
