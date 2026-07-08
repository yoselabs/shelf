# Runbook — onboard a consumer + the whole-codebase catch-up sweep

The **heavy, deliberately-invoked** operation: bring a project in as a shelf consumer *and* audit a
codebase that **predates the shelf** for generic substrate it hand-rolled before it could promote in the
moment. This is the **post-facto catch-up** for the aggressive promotion doctrine (resolution 0006) — for
*new* code, promotion happens at writing time (agent-loop.md §3), not here. Run it in a dedicated session,
not mid-feature.

**The prize is not "existing code shrinks."** It is **capitalizing every generic helper this codebase
hand-rolled into the shelf**, so the *next* project writes less custom code. A candidate qualifies on its
own merits — *generic substrate the catalog lacks* — **not** on whether a second consumer also has it.
Cross-consumer overlap is a nice confirmation, never a requirement. Promoting *grows* the shelf; that is
the point, and it never bloats a thin consumer (it keeps its own subset usage).

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

## Phase C — classify each candidate against the CATALOG (not against other consumers)

For each substrate candidate, compare it to **the shelf catalog** (`<shelf>/catalog/README.md` + packages)
and make one call: **is this generic substrate, or this app's business logic / product moat?**

- **Generic substrate** = helpers, utilities, patterns + their safety wrappers, adapters over awkward
  stdlib/library APIs, env/config loaders, a service's supporting functions. → a promote/adopt candidate.
- **Product** = the thing this app is *for* (a2web: bot-wall detection, proxy routing, browser stealth;
  a2kay: the vault model). → leave it. Rejecting product is correct, not a miss.

Cross-consumer overlap is **optional confirmation**, not a gate: if another consumer (`~/Workspaces/a2kay`,
etc.) hand-rolls the same thing, that only *raises confidence* it's generic. Where two consumers both have
an abstraction and one is a **superset** (async, cost accounting, more backends), promote the superset —
the arrow can **reverse** (a2web's `llm_extract.Provider` is richer than `anyllm`). But a lone n=1 generic
helper is a promote candidate on its own.

## Phase D — the per-candidate verdict

| Situation | Verdict | Action |
|---|---|---|
| Generic substrate the shelf **lacks** (even at n=1) | **PROMOTE** | Extract to the shelf (Phase E), born `candidate`. The default for anything generic. Growth of the catalog is the goal. |
| Shelf already provides it **and** it passes DEEP·STABLE·WINS for this consumer's real surface | **ADOPT** | git+tag source, `uv lock`, delete the hand-roll, publish `use-cases/<consumer>--<sw>.toml`, add a ledger entry. |
| Shelf provides it but the **contract shape is wrong** (Path vs string, sync vs async, drops needed data) | **EXTEND then adopt** | The friction *is* the promotion signal (constitution VII): grow the shelf piece a new capability (`convert_html(str,url)`), then adopt. If that's out of scope now, duplicate locally + log the gap. |
| The app's **business logic / product moat** | **KEEP** | Leave it. Not substrate. |

Promote is the **cheap default** for generic substrate — over-promotion is fixed later at reconciliation
(agent-loop §5b), a lost extraction moment is not. Only *adopting a dep* is conservative (DEEP·STABLE·WINS);
*promoting your own generic code into the shelf* is aggressive.

## Phase E — promote / extend (when Phase D says PROMOTE or EXTEND)

Follow **agent-loop.md §4** exactly, in the project's shelf worktree `../shelf-<project>`:
extract behind a Capability + boundary test + `candidate` Contract; `make check` green in the worktree;
tag namespaced; repoint **every** consumer that wants it (delete each in-repo copy, keep tests green); a
breaking change ships its migration. For a *superset* promotion that supersedes an existing thinner package,
the old package is `deprecated` (not deleted — Article VIII) with a migration note; consumers move opt-in.

## Phase F — record & report

- **Publish use-cases**: one `use-cases/<consumer>--<sw>.toml` per adopted piece (why + what — the retention claim).
- **Ledger**: append a `<seq>-<consumer>-<sw>-<event>.toml` per delivery/verdict; `make catalog`.
- **Report**: a table of every candidate → verdict → action, plus **what the shelf gained** — packages
  promoted / capabilities extended, i.e. generic substrate now available to the *next* project. The success
  metric is **future-code-avoided (catalog coverage), NOT existing-repo shrink.** A sweep that promotes a
  dozen helpers and shrinks no existing app by a line is a *success* — it just made the next app smaller.
  (A promoted piece may leave its origin app the same size until the app later adopts it back; that's fine.)

## Guardrails

- **Report before invasive change.** Phases B–D are read-only and produce the report; get human sign-off
  before deleting consumer code or cutting a promotion tag.
- **Cross-repo edits stay isolated:** consumer changes in the consumer repo; shelf changes in
  `../shelf-<project>`. Never edit the shelf main checkout.
- **`make check` green** in every repo you touch before you stop.
