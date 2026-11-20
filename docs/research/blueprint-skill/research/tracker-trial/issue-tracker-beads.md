# Issue tracker: beads

Draft of the `docs/agents/issue-tracker.md` blueprint would write for Matt Pocock's skills when the
tracker is beads (his setup's "Other" option). Each of his tracker operations is mapped to a `bd`
command. Trial file, 2026-10-10 — not yet run through `/to-spec`, `/to-tickets`, `/triage` or
`/wayfinder`.

Issues and specs for this repo live in beads (`bd`), a local Dolt database synced through the git
remote. Never edit `.beads/issues.jsonl` by hand; never use `bd edit` (it opens an editor).

## Conventions

- **Create an issue**: `bd create --title "..." --description "..." --type task|bug|feature|epic --priority 0-4`. Put acceptance criteria in `--acceptance`, design notes in `--design`.
- **Read an issue**: `bd show <id>` (add `--json` to parse).
- **List issues**: `bd list --status open --json`; filter with `--label`, `--type`, `--parent`.
- **Comment on an issue**: `bd comments add <id> "..."`.
- **Apply / remove labels**: `bd label add <id> <label>` / `bd label remove <id> <label>`.
- **Close**: `bd close <id> --reason "..."`.

## When a skill says "publish to the issue tracker"

- A **spec** (`/to-spec`): one bead, `--type epic`, the spec template as the description.
- **Tickets** (`/to-tickets`): one bead per ticket, `--parent <epic id>`, created blockers first;
  each blocking edge is `bd dep add <ticket> <blocker> --type blocks`.

## When a skill says "fetch the relevant ticket"

`bd show <id>`.

## Triage roles

| role | in beads |
|---|---|
| `needs-triage` | label `needs-triage` |
| `needs-info` | status `blocked` + a comment saying what is missing (waiting on a person, no bead to depend on) |
| `ready-for-agent` | status `open`, no open blocker — appears in `bd ready` |
| `ready-for-human` | label `ready-for-human` |
| `wontfix` | `bd close <id> --reason "wontfix: …"` |
| category `bug` / `enhancement` | `--type bug` / `--type feature` |

## Wayfinding operations

- **Map**: an epic bead holding the Notes / Decisions-so-far / Fog body.
- **Child ticket**: `bd create … --parent <map id>`, label `wayfinder:<type>`.
- **Blocking**: `bd dep add <child> <blocker> --type blocks` (native; `bd blocked` lists them).
- **Frontier**: `bd ready --parent <map id>` — open, unblocked, unclaimed, already computed.
- **Claim**: `bd update <id> --claim`, the session's first write.
- **Resolve**: `bd comments add <id> "<answer>"`, `bd close <id>`, then append a pointer to the map's
  Decisions-so-far with `bd update <map id> --append-notes "…"`.

## Not a Pocock role, kept from beads

- Shelved with a trigger: `bd defer <id> --reason "<trigger>"`.
- Link to a decision: `bd update <id> --spec-id docs/adr/NNNN-slug.md`.
