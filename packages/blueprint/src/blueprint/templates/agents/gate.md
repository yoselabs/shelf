# The gate

One command decides done. Humans, agents, hooks and CI all call the same one.

| item | value |
|---|---|
| Command | `just check` |
| Runs | format check, lint, types, spelling, dependency hygiene, tests with coverage, architecture rules, `just blueprint` (the stack list is in the stack file) |
| Passes when | exit 0; cross-file checks cover the whole repo, per-file linters the changed files (CI: everything), nothing else skipped |

## Changed files and the whole repo

Locally, a linter that judges one file at a time (formatter, per-file linter, shellcheck, hadolint, spelling) runs on
the files changed against the base: committed on the branch, staged, unstaged, untracked and not ignored; never a
deleted one. A linter with nothing to look at is skipped and says so in one line. A change to a linter's own
config runs it over everything. A check that reads across files (types, architecture, dependencies) always
covers the whole repo, and so does the gate in CI (`just check-all`). No base found means everything runs.

`blueprint recipe changed > tools/changed.py` copies the selector (stdlib only; `--help` documents it). It prints the
changed files matching its globs, NUL-separated, or everything on `--scope all`, when a `--config` file changed, or with
no base. A repo adds a `-changed` twin of each per-file recipe and `check` calls the twins:

```just
lint-changed:
    #!/usr/bin/env bash
    set -euo pipefail
    list=$(mktemp); trap 'rm -f "$list"' EXIT
    python3 -I tools/changed.py --config pyproject.toml --config ruff.toml 'src/*.py' 'tests/*.py' > "$list"
    [ -s "$list" ] || { echo "skipped lint: no Python file changed"; exit 0; }
    xargs -0 uv run ruff check --force-exclude < "$list"
    xargs -0 uv run ruff format --check --force-exclude < "$list"
```

`spell-changed` is the same with `--config .codespellrc` and `xargs -0 uv run codespell < "$list"`. Keep the whole-repo
`lint` and `spell`; `check-all` and CI call those.

## The runner

The gate is a `justfile`, and `just` is the runner (shelf ADR 0023). Pin it per repo: Python `uv add --dev rust-just`,
run as `uv run just check`; other stacks `uvx rust-just@<version>`, brew, or a CI setup action. A gate that is only a
Makefile fails `gate.runner`. Three rules keep the file readable by blueprint, which dumps the graph with
`just --dump --dump-format json`:

- No backticks: `just --dry-run check` evaluates them, and blueprint dry-runs `check`. Put anything that needs a command's output inside a recipe body.
- Loops and multi-line shell go in a shebang recipe (`#!/usr/bin/env bash`, then `set -euo pipefail`); just has no loops.
- A dependency, or a recipe argument that names a recipe (`check: (gate "check-host")`), is an edge in the graph.

## One box, many gates

Several agents share one machine, and each test run takes every core: on 2026-10-20 four gates at once on a 6-CPU box
took 11-14 min each instead of 2, and a push was killed. `blueprint recipe gate-state > tools/gate_state.py` copies the
script that prevents both halves of that (stdlib only; `--help` documents it):

| piece | in the justfile | does |
|---|---|---|
| the test lock | the test command runs as `python3 -I tools/gate_state.py lock -- <command>` | one test run per box at a time; a second gate waits and says who holds it. Off when `CI` is set or `GATE_LOCK=off` |
| the green record | `check` takes a first dependency running `gate_state.py start`, and its body runs `gate_state.py passed --gate check` | records the tree a green `check` saw, if no file changed during the run |
| the pre-push skip | the hook's entry is `python3 -I tools/gate_state.py pre-push --gate check -- uv run just check` | no second run when the working tree is clean and HEAD's tree is recorded; any doubt runs it |

Only the expensive step takes the lock, so the gate's parallel steps never wait on one another. `steps` points
`GATE_NOTICE_FD` at its terminal (`exec 3>&2; export GATE_NOTICE_FD=3`), so the "waiting" line shows while the step's
own output goes to its log. The record keys on the tree and the upstream merge-base: a rebase changes the tree, and the
gate runs again.

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
| pre-push | `bd hooks run pre-push`, `bd dolt push` (fatal; `BD_DOLT_PUSH_OPTIONAL=1` to push offline), then `just check` unless HEAD's tree already passed it | Heavy checks once per push, and not twice per tree |

After a clone, in this order, as plain commands (until `mise trust` every mise shim refuses, uv and just included):
`mise trust --yes && mise install --locked` (the exact tools mise.toml pins, from mise.lock; ADR 0024), the stack's sync
(python: `uv sync --locked`), `bd bootstrap` in a beads repo (its database comes from refs/dolt/data, not from git),
then `prek install`. A repo with LFS also needs `git lfs install --skip-repo` once per user. After a pin bump: `just tools`. Recipe: blueprint's `recipes/pre-commit-config.yaml`; bd hooks come first.

## Tool versions

Every tool the repo runs (uv, just, prek, bd, git-lfs, an engine editor) is pinned exactly in `mise.toml` and locked in
`mise.lock`; never install one with brew, apt or a curl script for this repo. A bump is a commit: edit the version, run
`mise lock`, commit both. `.python-version` (uv) and `global.json` (.NET) keep their own pins; mise does not pin them again.

## CI

CI runs `just check` and nothing else of its own. A CI step missing from `just check` is a gate gap: move it in.
CI gates the committed dependency set: install from the lockfile (`uv sync --locked`, `npm ci`), and let no step
before the gate edit a manifest or re-lock (`sed -i` on `pyproject.toml`, `uv lock`, `npm install`). A patch CI needs
is a commit.
CI reads the beads database before the gate: `bd bootstrap` with git's HTTPS rewrite of the SSH remote in its env
(`GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_0=ssh://git@github.com/`). A public repo rewrites to
`url.https://github.com/.insteadOf`; a private one carries the job token,
`url.https://x-access-token:${{ github.token }}@github.com/.insteadOf`, or the anonymous clone asks for a username.

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
