## Context

`docs/agent-loop.md` (143 lines) is read once per session, lazily, by every consumer agent — the
sole behavioral file every project's tiny resolver block points at. It is prose today: numbered
`##` sections with paragraphs. This change reshapes it into named workflows without changing what
it tells an agent to do, except for the specific gaps enumerated below, found by walking a real
design conversation against the loop's actual coverage.

Companion artifacts already exist and are NOT touched here: `docs/doctrine.md` (why),
`docs/constitution.md` (rules), `docs/resolutions/*.md` (decision records, ADR-style, each with an
`Expires:` date) — this change only adds one required field to that last one.

## Goals / Non-Goals

**Goals:**
- Every workflow in `agent-loop.md` is addressable by name (`WORKFLOW: PROMOTE`), has an explicit
  `TRIGGER:`, numbered `STEPS:`, and a stated `OUTPUT:` — no free paragraphs.
- Updating the loop itself becomes a named, repeatable workflow (`EVOLVE-THE-LOOP`), not an
  ad-hoc thing that happens when someone remembers.
- A resolution can no longer ship without recording whether/where it changed agent behavior.
- Close the three concrete operational gaps found this session: worktree staleness, fetch-cadence
  staleness bound, no upgrade-path artifact for consumers reconciling to a newer tag.

**Non-Goals:**
- Not renaming `resolutions/` → `adr/`.
- Not building the `anyllm.ProviderName` enum or touching any package code.
- Not building the advisory (non-blocking) expired-resolution scanner — noted as a follow-up only.
- Not changing `doctrine.md` / `constitution.md` content.
- Not re-litigating any of the four SEAM directions or the PROMOTE procedure's substance — only
  their *form*.

## Decisions

### D1 — Workflow block format

```
## WORKFLOW: <NAME>

TRIGGER: <one line — when an agent enters this workflow>

STEPS:
1. <imperative, terse>
2. <imperative, terse>
   - <sub-step if genuinely needed>

OUTPUT: <what state changed / what the agent now has>
```

Rationale: matches how the loop is actually consulted — an agent pattern-matches on "I am about to
X" (the trigger), then executes steps. Prose paragraphs bury the trigger inside a sentence;
this format puts it first and makes it greppable. Alternative considered: full YAML/JSON
pseudocode — rejected, still needs to be human-editable prose-adjacent markdown, and `##`-per-
workflow keeps it diffable in git and linkable (`agent-loop.md#workflow-promote`).

### D2 — Workflow inventory (carrying over existing substance)

| Workflow | Was (current §) | Change |
|---|---|---|
| `SESSION-RESOLVE` | §1 fetch cadence + implicit clone-if-absent from consuming-the-shelf.md | Reformatted; gains staleness bound (D4) |
| `SEAM` | §2 four directions | Reformatted only |
| `PRODUCE` | §3 promote-aggressively posture | Folded into `SEAM`'s PROMOTE direction — it was already describing the same trigger, kept as one workflow instead of two |
| `PROMOTE` | §4 procedure | Reformatted; gains worktree-freshness step (D5) and CHANGELOG requirement (D6) |
| `RECEIVE` | §5 | Reformatted; references CHANGELOG.md (D6) |
| `RECONCILE` | §5b | Reformatted only |
| `ESCAPE-HATCH` | §6 | Reformatted only |
| `EVOLVE-THE-LOOP` | — new | See D3 |
| (§7 "not in this loop") | kept as a closing note, not a workflow — it explicitly describes what is *out* of scope | Unchanged, stays prose (one paragraph, not worth a workflow shell for a negative statement) |

### D3 — `EVOLVE-THE-LOOP` workflow

```
TRIGGER: friction with this loop discovered mid-session — a gap, an unclear rule,
         a judgment call not covered.

STEPS:
1. Trivial / mechanical (typo, missing cross-link, obvious omission)?
   → fix agent-loop.md directly. Done.
2. Otherwise: write a resolution (docs/resolutions/000N-*.md) — the fork
   rejected, the reasoning, an Expires: date.
3. IN THE SAME CHANGE: distill the operational takeaway into the relevant
   WORKFLOW block here. Fill the resolution's `Distilled into:` field with
   the workflow name, OR `N/A — self-enforcing via <test/tool>` if this
   resolution doesn't change agent behavior at all.
4. Never split steps 2-3 across changes — a resolution merged without its
   distillation is incomplete, not "to be done later."

OUTPUT: agent-loop.md and its authoring resolution land in the same commit;
        make check enforces step 3 via the Distilled into: test (see D7).
```

Rationale: this is literally the PROMOTE workflow applied to methodology instead of code — same
shape (extract → tag/record → land atomically), reusing a pattern the reader already knows instead
of inventing new vocabulary. Alternative considered: a separate `docs/meta-loop.md` — rejected,
splitting it out just recreates the "will an agent remember to read the extra file" problem this
change exists to solve; it belongs inside the loop it governs.

### D4 — Fetch-cadence staleness bound

Current rule: "pull once, lazily, cache for the session." Add: **if the cached pull is older than
1 hour, re-pull before the next SEAM or PROMOTE workflow entry** (not on a fixed clock — checked
lazily, same spirit as the original rule, just bounded). 1 hour chosen as a round, generous bound —
long enough that a normal session never re-pulls twice, short enough that a long-running or
resumed session doesn't act on a half-day-stale clone. Not a hard science; revisit if it proves
wrong in practice (this is exactly what `EVOLVE-THE-LOOP` step 1 — trivial, mechanical — covers, no
resolution needed to retune a number).

### D5 — Worktree-freshness step in `PROMOTE`

Add as `PROMOTE` step 1 (before any file touch): `git -C ../shelf-<project> fetch && git rebase
origin/main` (or `pull --ff-only` if the branch has no local commits yet). Worktrees share git
objects but not branch position — a worktree opened days ago can be behind `main` with zero signal
that it is. Rejected alternative: relying on the existing push-rejected/rebase-retry step at the
*end* of PROMOTE (§4's current last paragraph) — that only catches the conflict at push time, after
work has already been done against a stale base; catching it on entry is cheaper.

### D6 — Package `CHANGELOG.md` convention

New file per package, `packages/<name>/CHANGELOG.md`. Format: one line per **contract-shape**
change only (not every release), arrow notation, no prose, no rationale:

```markdown
## 0.2.0
- LLMAdapter.complete(prompt) -> str  ⇒  LLMProvider.complete(*, user, system=(), ...) -> Completion
- silent "" on failure  ⇒  raises AnyLLMError
- sync  ⇒  async
```

Explicitly AI-facing: the audience is an agent deciding whether/how to reconcile a pin, not a human
reading release notes. Distinguished from adjacent artifacts by audience and content, not just
location:

| File | Answers | Audience |
|---|---|---|
| `ledger/00XX-*.toml` | Why did we build/adopt this, what did it cost | humans, audit |
| `catalog/<name>.toml` `notes` | What is this, right now | humans scanning the catalog |
| `packages/<name>/CHANGELOG.md` | What do I change to move between versions | an agent reconciling a pin |

`packages/anyllm/CHANGELOG.md` is written in this change as the worked example — backfilled from
the existing README migration table for v0.1.0 → v0.2.0. `RECEIVE` workflow gains a step: read
`CHANGELOG.md` first, before source or README, when a pinned package has a newer tag.

### D7 — `Distilled into:` field + blocking test

Resolution frontmatter gains a required line, alongside the existing `Status:` / `Expires:` /
`Track:`:

```
Distilled into: agent-loop.md#workflow-promote
```
or
```
Distilled into: N/A — self-enforcing via tests/test_boundary.py
```

New test, same shape/location pattern as `tests/test_catalog_projection.py` (which already keeps
`catalog/README.md` etc. from drifting from source manifests — a precedent for "a doc-consistency
rule enforced by a blocking pytest test, not a human habit"): iterate `docs/resolutions/*.md`,
assert each has a non-empty `Distilled into:` line. Fails `make check` if missing — no carve-outs,
per `AGENTS.md` §1.

Backfill for the 7 existing resolutions (decided during this change, not left as a TODO):
- `0001` repo-topology → `N/A — self-enforcing via the repo layout itself (packages/, catalog/, use-cases/, ledger/ existing as directories)`
- `0002` doctrine-homes-in-the-shelf → `N/A — self-enforcing via CLAUDE.md's read order`
- `0003` ontology-as-flat-files → `N/A — self-enforcing via tests/test_catalog_projection.py`
- `0004` linters-as-config-preset → `N/A — self-enforcing via docs/linting.md + Makefile`
- `0005` arch-rules-as-fitness-tests → `N/A — self-enforcing via tests/test_arch_rules.py`
- `0006` aggressive-capitalization → `agent-loop.md#workflow-seam` (PROMOTE direction) and `#workflow-produce`-turned-`#workflow-promote` per D2
- `0007` evolve-on-monotonic-contracts → `agent-loop.md#workflow-seam` (EVOLVE direction)

## Risks / Trade-offs

- **[Risk]** Reformatting 143 lines of prose into workflow blocks could silently drop nuance
  (a caveat that lived in a sentence, not a numbered step). → **Mitigation:** tasks.md requires a
  side-by-side content diff review (every existing rule must map to a step; nothing dropped, only
  reshaped) before this change is considered done, not just a format pass.
- **[Risk]** The 1-hour staleness bound (D4) is a guess, not measured. → **Mitigation:** explicitly
  flagged as retunable via `EVOLVE-THE-LOOP` step 1 (mechanical, no resolution needed) — not
  treated as load-bearing precision.
- **[Risk]** Backfilling `Distilled into: N/A` on 0001–0005 is itself a judgment call this change
  makes unilaterally. → **Mitigation:** each backfill cites the specific enforcing test/file, so
  it's checkable, not asserted; if wrong, fixing one line doesn't require touching the test.
- **[Trade-off]** `CHANGELOG.md` is a new file type added to the package convention with no prior
  precedent in this repo — slightly increases the "what files does a package need" surface.
  Accepted: the gap it closes (an agent reconciling a2kay from anyllm v0.1→v0.2 today has no file
  to read except the README's prose) is worse than the small addition.

## Migration Plan

Single change, no phased rollout — this is documentation/process, not a running system:
1. Rewrite `agent-loop.md` in place (D1–D3, D5, D6-reference).
2. Backfill `Distilled into:` on all 7 resolutions (D7) and the resolutions README template.
3. Add the blocking test (D7).
4. Write `packages/anyllm/CHANGELOG.md` (D6 worked example).
5. `make check` green.
6. No consumer action required — the resolver block each consumer carries already just says
   "read agent-loop.md," which is unchanged in location and entry contract.

Rollback: revert the commit; the resolver block contract is untouched so nothing downstream breaks
either direction.

## Open Questions

- Should `EVOLVE-THE-LOOP` itself eventually feed an advisory check for resolutions past their
  `Expires:` date (extending `make advisory`)? Noted as a follow-up, not built here.
- Is 1 hour the right staleness bound for D4, or should it instead be tied to "has another
  worktree pushed to main since I last pulled" (a fetch-and-compare, not a clock)? Left as the
  simpler clock-based rule for now; revisit if it proves wrong.
