# Domain language and decisions

| what | where | rule |
|---|---|---|
| Glossary | `CONTEXT.md` at the repo root | One canonical name per concept; each entry has a one-line definition and `_Avoid_:` names. Use these names in code, tests, beads and commits |
| Decisions | `docs/adr/NNNN-slug.md` | One decision per file, numbered, never renumbered |
| Decision index | `docs/adr/INDEX.md` | Generated from ADR frontmatter, one line per accepted ADR; never hand-edit. Read the index, then only the ADRs you need |

## CONTEXT.md

- Add a term the moment a concept needs a name; rename in code when a term changes.
- A term in two senses is two terms. Resolve it, do not footnote it.
- General engineering words keep their ordinary meaning; define only what is yours.

## ADRs

- Frontmatter: `id`, `title`, `statement` (one line, the decision), `concerns`, `status`, `decided_by`, `updated`.
- Body: the current decision on top; `## History` below, dated entries with trigger and who decided.
- Write one when a choice has two defensible answers and a cost, or when you overrule a default.
- Never edit an accepted decision silently: add a History entry or supersede it.
- Regenerate the index with the repo's script; the gate fails when it is stale.

Ask the owner before recording a decision as accepted; draft it as `proposed`.
