# docs as a system: thoughts → tracks → missions → resolutions

```
thoughts/     raw explorations (dated, unresolved, freely messy) — where thinking lands first
tracks/       a durable line of work (e.g. "topology", "contract-governance")
missions/     a scoped objective within a track — what OpenSpec changes attach to
resolutions/  decided things (ADR-style: the fork, the choice, the why, an expiry)
```

Thoughts feed tracks; tracks spawn missions; missions close into **resolutions**. A resolution with an
`expires:` date is a *belief with an expiry* — it must re-justify itself or decay.

The founding thinking (11 resolutions R1–R11, the full ontology, the adversary verdicts) lives in
`../thoughts/2026-07-07-shelf-exploration.md`. The resolutions here are the durable extract.

## Required frontmatter

Every resolution carries:

```
- **Status:** decided (YYYY-MM-DD)
- **Expires:** YYYY-MM-DD (re-justify at the half-year)
- **Track:** <track name>
- **Distilled into:** agent-loop.md WORKFLOW: <NAME>   |   N/A — self-enforcing via <test/tool>
```

`Distilled into:` is **mandatory** (`tests/test_resolution_distillation.py` fails `make check`
without it, no carve-outs). It forces the judgment call — does this decision change what an agent
*does* mid-session (→ name the workflow it was folded into, per `agent-loop.md` WORKFLOW:
EVOLVE-THE-LOOP), or is it purely structural/tooling, already enforced by a test or the repo layout
itself (→ `N/A`, name the enforcing thing). Never leave it blank "to fill in later."
