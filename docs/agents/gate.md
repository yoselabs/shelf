# The gate

One command decides done. Humans, agents, hooks and CI all call the same one.

| item | value |
|---|---|
| Command | `just check` |
| Runs | format check, lint, types, spelling, dependency hygiene, tests with coverage, architecture rules, `just blueprint` (the stack list is in the stack file) |
| Passes when | exit 0 over the whole repo (never only touched files), nothing skipped |

## The runner

The gate is a `justfile`, and `just` is the runner (shelf ADR 0023). Pin it per repo: Python `uv add --dev rust-just`,
run as `uv run just check`; other stacks `uvx rust-just@<version>`, brew, or a CI setup action. A gate that is only a
Makefile fails `gate.runner`. Three rules keep the file readable by blueprint, which dumps the graph with
`just --dump --dump-format json`:

- No backticks: `just --dry-run check` evaluates them, and blueprint dry-runs `check`. Put anything that needs a command's output inside a recipe body.
- Loops and multi-line shell go in a shebang recipe (`#!/usr/bin/env bash`, then `set -euo pipefail`); just has no loops.
- A dependency, or a recipe argument that names a recipe (`check: (gate "check-host")`), is an edge in the graph.

## Never bypass

| forbidden | do instead |
|---|---|
| `git commit --no-verify`, `git push --no-verify`, `SKIP=<hook>` | Fix the failure. If the check is wrong, change the check in its own reviewed commit |
| Deleting or weakening a test to go green | Fix the code; a test goes only with proof it guards nothing |
| Inline suppression | One scoped config line with a reason |
| "It fails on main too" | Still not done: fix it, or open a bead and tell the owner |

Why: a gate that can be waved through is not a gate. Only the owner may bypass.
## Hooks

prek owns the hooks, from `.pre-commit-config.yaml`. bd never installs its own (`bd init --skip-hooks`;
`bd hooks install` is never run): bd's hooks injected beside another manager's silently stop blocking commits.

| stage | runs | why here |
|---|---|---|
| pre-commit | `bd hooks run pre-commit`, then the stack's fast checks on staged files | Fast: seconds |
| prepare-commit-msg, post-merge, post-checkout | `bd hooks run <event>` | bd keeps its data in step |
| pre-push | `bd hooks run pre-push`, `bd dolt push` (non-fatal), then `just check` | Heavy checks once per push |

Install after clone: `prek install`. Recipe: blueprint's `recipes/pre-commit-config.yaml`; bd hooks come first.

## CI

CI runs `just check` and nothing else of its own. A CI step missing from `just check` is a gate gap: move it in.
CI gates the committed dependency set: install from the lockfile (`uv sync --locked`, `npm ci`), and let no step
before the gate edit a manifest or re-lock (`sed -i` on `pyproject.toml`, `uv lock`, `npm install`). A patch CI needs
is a commit.

## A gate in a container

When `just check` builds an image and runs inside it, `just blueprint` runs there too and judges only what the image
carries. The image's ignore file (`<Dockerfile>.dockerignore`, else `.dockerignore`) must keep every tracked file
blueprint reads: `justfile` (or `Makefile`), `AGENTS.md`, `.gitignore`, `.pre-commit-config.yaml`, `.beads/config.yaml`,
`.beads/.gitignore`, `.claude/settings.json`, `docs/blueprint/blueprint.toml`, `docs/agents/`, `.github/workflows/`.
Dropping `.beads` or `.claude` whole makes the container report a false "no tracker"; keep the folder out of the
context and re-include those files after it with `!.beads/config.yaml` lines. `gate.runs-blueprint` names a dropped file.

## Exceptions

An exception to a blueprint rule (an override, an ignored path in `docs/blueprint/blueprint.toml`) carries a reason and
either `expires = <date>` or `adr = "NNNN"`, an accepted ADR in `docs/adr/` that records the durable decision. The gate
reports an exception with neither, or naming an ADR that is missing or not accepted.

## Adding a check

Plant a violation, see the gate fail, add the check to `just check` (a hook only if it takes seconds), remove the violation, see green.
