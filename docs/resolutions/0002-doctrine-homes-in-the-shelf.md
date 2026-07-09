# 0002 — Doctrine homes in the shelf; consumers reference it, if necessary

- **Status:** decided (2026-07-08)
- **Expires:** 2027-01-08 (re-justify at the half-year)
- **Track:** governance
- **Distilled into:** N/A — self-enforcing via CLAUDE.md's read order

## Decision

The shelf is the **single, self-contained home** of its own operating model. Everything the shelf
knows about how it works is authored and versioned *here* — not in Kay or any external knowledge base:

- **Doctrine & vocabulary:** `doctrine.md`, `constitution.md`, `glossary.md`.
- **Behaviour:** `agent-loop.md` (the standing loop every consumer's agent self-applies) and
  `consuming-the-shelf.md` (onboarding).
- **Decisions & scope:** `resolutions/`, `missions/`.

Other software pieces (consumers) **reference** it, and only *if necessary* — via the tiny resolver
block pasted into their own `AGENTS.md`/`CLAUDE.md`, which resolves the local shelf clone and reads
`agent-loop.md`. No consumer, and no agent, must open Kay to build correctly.

This supersedes the exploration doc's original plan ("doctrine + ontology → Kay"). The rejected reason:
a knowledge base is the wrong home for a model that is *enforced* by this repo's git hooks, tests, and
CI. Doctrine lives where it is executed.

## Hard rules

- **Define once, in the shelf.** A rule or vocabulary term is authored in `docs/`, never duplicated
  into a consumer. Consumers carry only the pointer.
- **Kay is not a runtime dependency.** The shelf may *credit* prior research (e.g. R154) as lineage,
  but nothing in the shelf requires reading an external base to be understood or used.
- **Reference, don't copy.** When a consumer needs the model, it links to the shelf doc; it does not
  restate it (restating drifts — constitution I).
