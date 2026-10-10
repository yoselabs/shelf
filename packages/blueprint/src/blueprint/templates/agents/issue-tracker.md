# Issue tracker: beads

Issues and specs live in beads (`bd`), a local Dolt database synced through the git remote.
Never edit `.beads/issues.jsonl` by hand; never use `bd edit` (it opens an editor). Use `bd` for
work tracking only, never for project memory (`bd remember` is not used).

## Operations

| operation | command |
|---|---|
| Create | `bd create --title "..." --description "..." --type task\|bug\|feature\|epic --priority 0-4`; criteria in `--acceptance`, design notes in `--design` |
| Read | `bd show <id>` (`--json` to parse) |
| List | `bd list --status open --json`; filter `--label`, `--type`, `--parent` |
| What is workable | `bd ready` (open, unblocked, unclaimed) |
| Claim | `bd update <id> --claim`, the session's first write |
| Comment | `bd comments add <id> "..."` |
| Label | `bd label add <id> <label>` / `bd label remove <id> <label>` |
| Close | `bd close <id> --reason "..."` |
| Link to a decision | `bd update <id> --spec-id docs/adr/NNNN-slug.md` |
| Provenance | `bd update <id> --set-metadata branch=<name> --set-metadata commit=<sha>` |
| Supersede | `bd dep add <new> <old> --type supersedes`; never delete the old bead |

## Specs and tickets

| artefact | in beads |
|---|---|
| A spec | one bead, `--type epic`, the spec as description |
| A ticket | one bead per ticket, `--parent <epic id>`; each blocking edge `bd dep add <ticket> <blocker> --type blocks`, blockers created first |
| Fetch a ticket | `bd show <id>` |
| Map of open questions | an epic bead holding notes, decisions so far, fog; children are tickets with label `wayfinder:<type>`; frontier is `bd ready --parent <map id>`; resolve with a comment, close, then `bd update <map id> --append-notes "..."` |

## Triage roles

| role | in beads |
|---|---|
| needs-triage | label `needs-triage` |
| needs-info | status `blocked` plus a comment saying what is missing |
| ready-for-agent | status `open`, no open blocker (shows in `bd ready`) |
| ready-for-human | label `ready-for-human` |
| wontfix | `bd close <id> --reason "wontfix: ..."` |
| category | `--type bug` / `--type feature` |

## Not ready, three kinds

Blocked by a bead: `bd dep add ... --type blocks`. Shelved: `bd defer <id> --reason "<trigger>"`.
Waiting on a person or access: `--status blocked` plus a comment. Do not collapse them.

## Config traps

- Every open bead needs acceptance criteria before it is ready; `bd lint` in the gate enforces it.
- `bd config set` edits the tracked `.beads/config.yaml`; a `git checkout` silently reverts it. Read back with `bd config get <key>`.
- Hooks are prek's, not bd's ([gate.md](gate.md)).
