# Domain language and decisions

| what | where | rule |
|---|---|---|
| Glossary | `CONTEXT.md` at the repo root | One canonical name per concept; each entry has a one-line definition and `_Avoid_:` names. Use these names in code, tests, beads and commits |
| Decisions | `docs/adr/NNNN-slug.md` | One file per decision topic, numbered, never renumbered. Living: rewritten when the decision changes |
| Decision index | `docs/adr/INDEX.md` | Generated from ADR frontmatter, one line per decision in force; never hand-edit. It is all you need to work: open an ADR only to challenge or change it |

## CONTEXT.md

- Add a term the moment a concept needs a name; rename in code when a term changes.
- A term in two senses is two terms. Resolve it, do not footnote it.
- General engineering words keep their ordinary meaning; define only what is yours.

## ADRs

- Frontmatter: `id`, `title`, `statement` (one line, the decision as it stands), `concerns`, `status`
  (proposed/accepted/superseded/rejected), `decided_by`, `updated`.
- Body, short: the decision and why on top; rejected options, one line each with the reason;
  `## History` below: dated entries, each with what changed, the trigger, and why the dropped choice was dropped.
- Changing a decision: rewrite the top, move the old decision into History. Do not open a new ADR for
  the same topic; that splits its history.
- Write one when a choice has two defensible answers and a cost, or when you overrule a default.
- After any ADR change: `blueprint adr-index --repo . --write`; the gate fails on a stale index.

Ask the owner before recording a decision as accepted; draft it as `proposed`.
