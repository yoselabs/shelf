---
id: 0017
title: Decisions are living ADRs; agents read a generated index
statement: CONTEXT.md is the glossary; each decision topic is one docs/adr/NNNN-slug.md, rewritten when it changes with the old choice in its History; agents read only the generated docs/adr/INDEX.md.
concerns: [knowledge]
status: accepted
decided_by: owner
updated: 2026-10-11
distilled_into: blueprint knowledge.glossary, knowledge.adr-format, knowledge.adr-index; templates/agents/domain.md
---

# 0017 — Living ADRs and a generated index

## Decision

- **Glossary:** `CONTEXT.md` at the root (Matt Pocock's convention); `CONTEXT-MAP.md` when there are several contexts.
- **One file per decision topic:** `docs/adr/NNNN-slug.md`. When the decision changes, rewrite the
  top and move the dropped choice, its trigger and why it was dropped into `## History`. No new ADR
  for the same topic: that splits its reasons.
- **Short:** frontmatter (`id`, `title`, `statement` ≤200 chars, `concerns`, `status`, `decided_by`,
  `updated`), the decision and why, rejected options one line each, then History.
- **Index:** `docs/adr/INDEX.md`, generated (`blueprint adr-index --write`), one line per decision in
  force, grouped by concern. It is all an agent needs to work; an ADR file is opened only to
  challenge or change its decision. The gate fails on a stale index.

## Rejected

- Immutable ADRs superseded by new ones: hundreds of files, and the reason for a change is spread across them.
- Agents reading every ADR: tokens spent on history that matters only when challenging.

## History

- 2026-10-11: built as the knowledge concern (shelf-1y4.6, shelf-u43); the shelf moved
  `docs/resolutions/` to `docs/adr/` and `docs/glossary.md` to `CONTEXT.md`.
