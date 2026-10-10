# Working with agents

How an agent (or a person) works in this repo, session start to handoff.

## Session loop

| step | do | why |
|---|---|---|
| 1 | Read AGENTS.md, then only the `docs/agents/` files its block says apply | Context is the scarce resource; read by trigger |
| 2 | `bd ready`; pick one bead; `bd update <id> --claim` as the first write | A claim stops two agents taking one task |
| 3 | Read the bead's acceptance criteria; none means ask, do not guess | Criteria are the definition of the task's done |
| 4 | Work test first ([testing.md](testing.md)); keep to files the bead needs | Disjoint files make parallel work safe |
| 5 | `make check` green over the whole repo | [gate.md](gate.md) |
| 6 | `bd close <id> --reason "..."`; new work found becomes a new bead | Nothing stays only in chat |
| 7 | Report: files changed, gate result, bead state, next command | The owner reads the report, not the diff |

## Worktrees: one agent, one checkout

Every agent session works in its own git worktree, on its own branch. The main checkout is the owner's.
Why: a commit hook hides every uncommitted edit while it runs, then restores it; another agent's write
in the same folder during that time is lost, and the commit fails (reproduced with prek, 2026-10-11).

| step | do |
|---|---|
| start | the harness's worktree mode (Claude Code puts them in `.claude/worktrees/`), or `git worktree add .worktrees/<name> -b <branch>` |
| set up | the stack's sync in the new tree (python: `uv sync`); nothing is copied from the main checkout |
| beads | `bd` in a worktree uses the main checkout's database; never `bd init` there |
| hooks | prek's hooks are installed once for the repo and run in every worktree; never install per worktree |
| finish | `make check` green in the worktree; on the owner's yes, rebase on main and merge fast-forward; then `git worktree remove` |

Both folders are git-ignored (`agents.worktrees`), so no linter, test run or `git add -A` reaches into another tree.

## Beads: the three "not ready" states

| situation | use |
|---|---|
| Waiting on another bead | `bd dep add <id> <blocker> --type blocks` (status stays open; `bd blocked` lists it) |
| Shelved on purpose, nothing blocking | `bd defer <id> --reason "<the trigger>"` (a deferral without a named trigger is incomplete) |
| Waiting on a person or access with no bead | `bd update <id> --status blocked` plus a comment saying what is needed |

Never invent a blocker bead for "not started". Commands: [issue-tracker.md](issue-tracker.md).

## Rules

| rule | why |
|---|---|
| Commit and push only on the owner's explicit yes, per request | A commit is shared history; one yes is not a standing yes |
| Use Sonnet-class agents for legwork (search, bulk edits, research reading); keep judgement and design in the main session | Cost and speed; legwork needs no deep reasoning |
| Give a helper the goal, the files, what is ruled out, and "do not commit" | A helper knows only its brief |
| No TODO files, no `TODO` comments without a bead id, no markdown task lists | One tracker, one truth |
| No memory files for project facts: put them in ADRs, CONTEXT.md or a bead | Hidden memory forks the truth |
| A "done" report names what was run; "untested" and "not done" are stated, never implied | Done must be checkable |
| Stop and ask when a rule here blocks the task; never route around it | Rules change by decision, not by evasion |

## After a blueprint run

- Fill the survey: `blueprint survey --repo . > docs/blueprint/survey.md`, answer every row with one line of
  evidence, then `blueprint survey --check docs/blueprint/survey.md` must print `complete`.
- Answer as a critic of the run: a "yes" without evidence is a "partly".
- A gap in blueprint itself (no profile, no checkpoint) becomes one bead in the shelf repo, titled
  `blueprint lacks: <what>`; never patch blueprint from inside this repo.
- Tell the owner the survey path in one line, to relay to the shelf.
