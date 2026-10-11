# docs as a system: thoughts → tracks → missions → ADRs

```
thoughts/     raw explorations (dated, unresolved, freely messy) — where thinking lands first
tracks/       a durable line of work (e.g. "topology", "contract-governance")
missions/     a scoped objective within a track — what OpenSpec changes attach to
adr/          decisions: living ADRs, one file per topic
```

Thoughts feed tracks; tracks spawn missions; missions close into **ADRs**. An ADR with an
`expires:` date is a *belief with an expiry* — it must re-justify itself or decay.

## How ADRs work

- **Living, one file per topic.** `docs/adr/NNNN-slug.md`. Numbers and slugs are stable.
- **Rewritten when the decision changes.** The body states the decision as it stands. The old
  choice, the trigger and why it was dropped go into the file's `## History` as a dated bullet.
- **Agents read `docs/adr/INDEX.md` only.** It is generated (`blueprint adr-index --write`) from
  the frontmatter: one line per decision in force. Open an ADR file only to challenge or change it.
- **Short.** Decision on top, rejected options with their reasons, then History.

## Frontmatter

```
---
id: "0007"
title: <the decision, short>
statement: <ONE line, at most 200 characters: the decision as it stands, plain words>
concerns: [doctrine, packaging, tooling, gate, skills, workflow]   # a small consistent set
status: accepted            # proposed | accepted | superseded | rejected
decided_by: owner
updated: YYYY-MM-DD         # the latest date in the file
expires: YYYY-MM-DD         # optional: re-justify by then
distilled_into: <the agent-loop.md WORKFLOW it was folded into>   |   N/A — self-enforcing via <test/tool>
---
```

`distilled_into` is **mandatory** (`tests/test_adr_distillation.py` fails `make check` without it,
no carve-outs). It forces the judgment call: does this decision change what an agent *does*
mid-session (→ name the workflow it was folded into, per `agent-loop.md` WORKFLOW:
EVOLVE-THE-LOOP), or is it purely structural/tooling, already enforced by a test or the repo layout
(→ `N/A`, name the enforcing thing). Never leave it blank "to fill in later."

The founding thinking (11 decisions R1–R11, the full ontology, the adversary verdicts) lives in
`../thoughts/2026-07-07-shelf-exploration.md`. The ADRs here are the durable extract.

History: until 2026-10-11 these files lived in the `docs/resolutions` folder, one frozen file per decision, with
`Status`/`Expires`/`Track` lines. The 2026-07-09 choice to keep that name (it carried the pipeline
stage) was dropped when blueprint's knowledge layout (`docs/adr/`, generated INDEX) became the
repo-wide standard.
