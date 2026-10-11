---
id: 0019
title: One agent per git worktree
statement: Every agent session works in its own worktree and branch; worktree folders are git-ignored; no worktree stays more than a day out of step with main, either way.
concerns: [agents]
status: accepted
decided_by: owner
updated: 2026-10-11
distilled_into: blueprint agents.worktrees, agents.worktrees-in-sync; templates/agents/working-with-agents.md
---

# 0019 — One agent per worktree

## Decision

Each agent session gets its own worktree. bd shares the main database through git's common dir;
prek's hooks install once and run in every worktree; the container gate mounts the main `.git`
read-only when run from a worktree.

Merge often: rebase on main at least daily and merge finished slices to main the same day, so no
worktree is more than a day behind main or holds work unmerged for more than a day. A long task
lands in small merged steps.

Why: a commit hook hides uncommitted edits while it runs and restores them after; a second agent
writing in the same checkout loses its write and the commit fails (reproduced with prek 0.3.6).
Every hook manager that stashes does this.

## Rejected

- Several agents in one checkout with care: the loss is silent, care does not see it.

## History

- 2026-10-11: decided.
- 2026-10-11: added the one-day sync rule (owner): drifting worktrees turn merges into conflict work
  and let agents build on a main that no longer exists.
