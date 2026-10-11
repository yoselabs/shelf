---
id: 0002
title: Doctrine homes in the shelf
statement: The shelf is the single self-contained home of its own operating model; consumers only point to it, and no external knowledge base is needed to use it.
concerns: [doctrine]
status: accepted
decided_by: owner
updated: 2026-10-11
expires: 2027-01-08
distilled_into: N/A — self-enforcing via CLAUDE.md's read order
---

# 0002 — Doctrine homes in the shelf; consumers reference it, if necessary

## Decision

The shelf is the **single, self-contained home** of its own operating model. Everything the shelf
knows about how it works is authored and versioned *here*, not in Kay or any external knowledge base:

- **Doctrine & vocabulary:** `doctrine.md`, `constitution.md`, `CONTEXT.md`.
- **Behaviour:** `agent-loop.md` (the standing loop every consumer's agent self-applies) and
  `consuming-the-shelf.md` (onboarding).
- **Decisions & scope:** `adr/`, `missions/`.

Consumers **reference** it, and only *if necessary*, via the tiny resolver block pasted into their
own `AGENTS.md`/`CLAUDE.md`, which resolves the local shelf clone and reads `agent-loop.md`. No
consumer, and no agent, must open Kay to build correctly.

Hard rules:

- **Define once, in the shelf.** A rule or vocabulary term is authored in `docs/`, never duplicated
  into a consumer. Consumers carry only the pointer.
- **Kay is not a runtime dependency.** The shelf may *credit* prior research (e.g. R154) as lineage,
  but nothing in the shelf requires reading an external base to be understood or used.
- **Reference, don't copy.** A consumer links to the shelf doc and never restates it (restating
  drifts, constitution I).

## Rejected

- **Doctrine + ontology in Kay** (the exploration doc's original plan): a knowledge base is the wrong
  home for a model that is *enforced* by this repo's hooks, tests and CI. Doctrine lives where it is
  executed.

## History

- 2026-07-08: decided; supersedes the exploration doc's plan "doctrine + ontology → Kay". Expires
  2027-01-08. Track: governance.
- 2026-10-11: the vocabulary file moved from `docs/glossary.md` to the root `CONTEXT.md`, and
  the `resolutions` folder became `adr/` (blueprint knowledge layout). The decision itself is unchanged.
