# Design

## D1 — The split: prose for judgment, execution for order and effect

**Decision.** The skill chooses operations. The operations enforce ordering and assert results.
No ordering constraint is expressed only in the skill's text.

The tension this resolves is real and worth stating, because the obvious objection to "write a
skill" is correct: a skill is prose instructions to an agent, and this session's finding is that
prose cannot enforce ordering or verification. A skill that walks an agent through ordered steps
is the same failure in a new file.

The way out is that onboarding contains two genuinely different kinds of knowledge:

| | judgment | mechanism |
|---|---|---|
| example | "does this repo already use husky?" · "does it want beads?" · "is this greenfield?" | "the guard must be installed before `bd init`" · "confirm the hook actually blocks" |
| varies per repo | yes — that is the point | no — identical everywhere |
| can prose carry it? | **yes** — it is weighing, not sequencing | **no** — the entire lesson of this session |
| home | the skill | the operation |

Prose is not the problem; prose in the wrong role is. Asking an agent to weigh a repo's situation
is what agents are for. Asking one to remember step 7 of 14 is what failed four times this
session.

**The mechanism that makes this hold: ordering is a precondition, not a sequence.** The `beads`
operation does not run "after" the `guard` operation because the skill invokes them in that
order. It refuses to run at all unless `guard` has completed and verified. Consequences:

- The skill can be wrong, stale, half-read, or replaced by a different agent, and the ordering
  still holds.
- A human running the operations by hand gets the same protection.
- `make bootstrap` (`shelf-abf`) calling them gets it for free, with no duplicated ordering logic.

That last point is why the operations, not the Make target, are the shared substrate.

## D2 — Why operations, and why they live in shelf

**Decision.** A small operations module in shelf, run in the target repo's root. Precedent:
`tools/hooks/install.py` is already exactly this.

Greenfield forces it. `shelf-abf`'s `make bootstrap` cannot be the entry point for a repo whose
Makefile arrives *during* onboarding — the Makefile is an output of the process, not an input.
Something must run before the target has anything, and it has to come from shelf.

On resolution 0004 ("linters are a config preset, not a CLI"), which this looks like it violates:
0004's objection is to a **runtime dependency** — a program a consumer must keep installed and
version-matched to build its code. A one-shot operation that copies config in and exits is not
that. It leaves no import, no pin, no version coupling; the consumer owns the copy afterward,
exactly as 0004 requires. The distinction is *scaffold* versus *runtime*, and it should be stated
in the change rather than left for someone to litigate later.

Operations are **tagged by stack**, not abstracted over it:

```
stack-agnostic:   guard · resolver-block · beads · verify
python+uv:        linter-preset
```

Per the answer to scoping, only `python+uv` is implemented. The tag is the seam a second stack
would attach to. Building the abstraction now, for a stack that does not exist, is precisely what
the constitution forbids — and an abstraction derived from one instance would be wrong anyway.

## D3 — What each operation must guarantee

Every operation, without exception:

1. **Idempotent** — running it twice changes nothing the second time.
2. **Precondition-checked** — refuses, loudly, if what it depends on is not present *and verified*.
3. **Effect-asserting** — confirms what it intended, by exercising it. Never by checking that a
   file exists, a marker is present, or a mode bit is set. (`fix-guard-hookspath-resolution` D2 is
   the worked example; every cheap check passed while this repo was unguarded.)
4. **Three-outcome** — applied / failed / could-not-apply, distinct. "Could not check" reported as
   success is how a dead guard printed `✔`.
5. **Non-destructive by default** — an operation that would overwrite something it does not own
   refuses and reports, per `fix-guard-hookspath-resolution` D3.

Guarantee 2 is what carries the ordering. Guarantee 3 is what makes guarantee 2 trustworthy —
a precondition satisfied by an artifact rather than an effect is the exact bug being designed out.

## D4 — The skill's judgment surface

What the skill decides, and what it must not:

**Decides (adaptive):**
- Greenfield vs established repo — the latter may need the catch-up sweep, which is separate work.
- Which hook manager, if any, already owns the repo (`git rev-parse --git-path hooks`, plus marker
  detection). Determines whether beads will chain or seize, and whether onboarding should proceed.
- Whether beads is wanted. Default **yes** — most repos here will use it — and opt-out, not a
  separate runbook nobody reaches.
- What already exists and must be merged rather than written (an existing `Makefile`, existing
  ruff config, an `AGENTS.md` with content).
- Non-Python target: run the stack-agnostic operations, and **say plainly** which parts are not
  available rather than half-applying a Python preset.

**Must not decide:**
- Operation order. That is D1.
- Whether verification passed. An operation reports; the skill relays.
- Whether to add shelf dependencies. `onboard-a-consumer.md` Phase A step 4 is deliberate — a dep
  is added when the sweep says *adopt*, never as an onboarding side effect. The skill must not
  helpfully add one.

## D5 — The resolver block stops being a paste

**Decision.** Marker-delimited and re-projectable, not copied prose.

Today `consuming-the-shelf.md` §3 says "paste this block into the project's AGENTS.md". A pasted
block drifts silently the moment the source changes, across every consumer, with no way to detect
it — the constitution's "files are truth; indexes are derived" applied to a doc fragment, and
currently violated.

Marker-delimited means the operation can re-project it, and a consumer can be checked for drift.
This is the pattern `bd init` already uses on `AGENTS.md`, and this session confirmed it survives
a symlinked `CLAUDE.md` correctly — so the shape is proven in this exact position.

Note the interaction: shelf's own `AGENTS.md` now carries two bd-managed marker pairs. A third
(shelf's resolver block) is fine — they are independent regions — but the operation must append
outside every existing managed block, never inside one.

## Open questions

- **Do a2kay and a2web need re-onboarding?** Both were onboarded by the manual path, before any
  of this was known, so both may carry landmines 2–6. The operations are idempotent, so running
  them is safe — but it is a deliberate act with a real chance of finding something, not a
  formality. Out of scope here; worth a bead once the operations exist.
- **Where does the skill physically live?** `.claude/skills/` is Claude-specific; `.agents/skills/`
  is the cross-tool location `bd` chose. Onboarding should not assume the consumer's agent
  runtime. Decide during implementation, with a bias toward the cross-tool path.
- **Does `verify` belong in the consumer's `make check`?** By `bootstrap-target-contract` D4 the
  answer splits: content assertions yes, environment assertions no. The onboarded repo should
  inherit that split rather than a single blunt check. Confirm when `shelf-abf` is re-scoped.
