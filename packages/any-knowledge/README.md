# any-knowledge

Knowledge a repo keeps, apart from the blueprint gate (blueprint checks none of it).

| verb | does |
|---|---|
| `python -m any_knowledge index [--write]` | print or write `docs/adr/INDEX.md`, one line per decision in force |
| `python -m any_knowledge check [--glossary]` | exit 1 on a malformed ADR, a stale index, or (asked) a missing CONTEXT.md |
| `python -m any_knowledge seed [--stack S] [--framework F] [--beads]` | copy the missing `docs/agents/*.md` and keep the AGENTS.md managed block |

A repo adopts it by running `check` from its `check-extra` recipe; a repo with no `docs/adr/` runs nothing. Temporary package: the name and home are the owner's call.
