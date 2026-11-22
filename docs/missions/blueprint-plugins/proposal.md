## Why

Blueprint is meant to be used by repos that are not ours, and each of them should choose what it wants. Today every row is either always
asked or asked when a detector fires, and the only off switch is a justified per-row override in `blueprint.toml`. Our own conventions
(beads, mise, `bd sync` hooks) are mixed into topic modules (`backlog.py`, `hooks.py`, `gate_*.py`, `agents.py`), so "everything about
beads" cannot be turned off, shown, or handed to someone else as one thing. Bead: shelf-ysmh. Owner intent 2026-11-21.

## What changes

- A **plugin** is the unit a repo chooses: python, uv (inside python), dotnet, node, go, rust, nix, compose, dockerfile, shell,
  beads, mise, secrets, git-hooks (prek), gate (just and any-gate), agents (AGENTS.md, worktrees), plus the framework profiles.
- Each plugin has a **default state**: `detected` (on when repo files say so), `on` (asked unless the repo opts out), `off` (asked only
  when the repo opts in). Our own conventions ship `on`; stacks ship `detected`; anything experimental ships `off`.
- A plugin **requires** other plugins (uv requires python; the `bd sync` hooks require beads and git-hooks). Switching a plugin off
  switches its dependents off, with a notice that names why.
- A repo's `blueprint.toml` holds one switch per plugin; the per-row override stays for a single row.
- Someone else can ship a plugin (a manifest plus rows) without editing blueprint's own modules.

## Not yet

Moving the code. First the manifest as data over today's modules, with no change in what any repo is asked.
