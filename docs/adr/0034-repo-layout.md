---
id: 0034
title: Repo layout: one code base at the root, two in backend/ and frontend/
statement: One code base stays at the repo root; two code bases each live in backend/ and frontend/ with the root holding repo-level files only; a workspace needs a second package; the contract between stacks is a file.
concerns: [gate, packaging]
status: accepted
decided_by: owner
updated: 2026-11-28
distilled_into: N/A — self-enforcing via the blueprint audit row layout.stacks-in-own-folders and the per-stack-root gate render
---

# 0034 — Repo layout

Owner decision 2026-11-28 (bead shelf-e722; a2kay is the first repo to move).

## Decision

- **One code base** (node used only as a tool, for example Tailwind or a bundler step) stays at the repo root.
- **Two code bases** (each with its own dependencies, tests and build: a Python backend and a TypeScript frontend) each live in a folder named exactly `backend/` and `frontend/`. The root holds repo-level files only: `justfile`, `AGENTS.md`, `mise.toml`, `.blueprint/`, `docs/`, deploy files (`Dockerfile`, compose).
- **A workspace** (uv or pnpm) appears when a stack gets its second package, never for one package.
- **`packages/` holds libraries**, never an app.
- **The contract between stacks is a committed file** (an `[[edge]]` `via`), never a package both import.
- **Blueprint** detects a stack at the root or one folder down, judges each root with its own profile, and renders each stack's gate steps to run in its folder. A step reads only its own folder, so a frontend edit runs no Python step. The audit row `layout.stacks-in-own-folders` fails a repo with two code bases where one sits at the root and names the `git mv` fix; a repo may waive it (ADR 0018).
- A "code base" is a language-family stack (the `family` of its profile) except `node-tooling`, which is a tool.

## Rejected

- **Options** (`src/`, `server/`, `ui/`, `apps/*`): the owner wants one rule. Folder names are fixed.
- **A workspace for two stacks of different languages**: the stacks share no package manager; a workspace would be a root file for nothing.
- **A config-only root `pyproject.toml`** to keep the engine reading the root: it hides where the code is; the engine learns the stack roots instead.

## History

- 2026-11-28: decided by the owner; a2kay (Python at root + `ui/`) is the reference case.
