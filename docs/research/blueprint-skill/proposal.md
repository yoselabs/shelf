## Why

Every new project re-derives its setup from memory, and every derivation misses something different.
Two kickoffs on 2026-10-10 (a2peer, lifesim) each produced a hand-written checklist; neither covers
the other. a2kay, set up without one, measured the cost afterwards (2026-10-08 → 10-10):

- ~3,400 unit tests with no layering strategy; 39 of 71 closed bugs were workflow-shaped, and a unit
  test had found 1 of the 71.
- 67% of feature commits added a new test file instead of extending one; 24 test files were named
  after a change.
- 8 clusters of the same behaviour asserted at several layers; a 720-row matrix where 20 rows killed
  every mutant the 720 did.
- The gate took ~340 s on macOS, 64 s in a Linux container.

(Numbers from the a2kay testing handoff (session input, not in the repo); to be re-verified against
the a2kay sources before they enter the skill.)

The owner's framing, 2026-10-10, verbatim:

> "Every software should start with a shelf repository running that skill. And shelf is ultimately
> kind of software universe, right? That's why it dictates the experience of how all AI factories
> and agents should work."

So the ideal setup of a repo is shelf doctrine, and it needs one home that every project runs.

## What changes

- A new `Kind: skill` member, `skills/blueprint/` — the first real skill on the shelf (closes
  `shelf-uvf`, which exists to exercise the skill-kind contract end to end).
- **One checklist, one mode.** Blueprint audits a repo against the ideal setup. An empty repo is a
  repo where every checkpoint fails; an existing repo may fail enough to restructure from scratch.
  Owner decision, 2026-10-10: *"I'm not seeing that those should differ much… even existing repo
  might need to restart things from scratch"*. A new repo gets extras on top: the phase order,
  templates, and the research and spike steps that come before code.
- Areas it covers, independent of tech stack: shaping and decisions before code, naming, workspace
  hygiene, backlog (beads), requirements (openspec), decision records (a2kay vault, ADR-style),
  shelf onboarding and the reuse loop, stack choice and pins, linter strictness, architecture
  layering enforced by a tool, testing (behaviour-first), the gate (`make check`), Docker and CI,
  agent instructions (AGENTS.md), release and operations.
- Per-stack packs loaded only for the stack in use: `python-uv` first.

## Scope

**In:** what a repo must contain and enforce; the kickoff phases a new project goes through; the
gate-review procedure (design D1).

**Pending owner answer (design D3):** standing agent conduct — question format, escalation,
worktree per agent, commit policy — moves out to the shelf resolver block, `docs/agent-loop.md`
and the owner's global instructions; blueprint checks only that the resolver block is current.

**Out:**
- How an orchestrating agent runs many subagents (handoff Addendum 2 "Running many agents": prompt
  shape, mid-flight correction, ETAs). That is agent practice, not repo content. Pointer: a separate
  skill or the owner's global instructions; not decided here.
- Re-describing what other pieces already do: `make bootstrap` / `onboard-consumer` (wiring),
  the `beads` skill, the openspec skills, `docs/agent-loop.md` (SEAM / PROMOTE). Blueprint calls
  them and checks their effect.
- Stack packs other than `python-uv` and a provisional `dotnet`, until a project needs one.

## Impact

- New: `skills/blueprint/` (SKILL.md, references, evals), `catalog/blueprint.toml`.
- Probably new: beads for promoting a2kay's test-pruning and lineage scripts to the shelf, which
  the testing area depends on.
- Touches: `tests/test_gate_covers_every_skill.py` gains a population floor once a skill exists
  (its own docstring asks for that).
