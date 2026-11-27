# The gate

One command decides done. Humans, agents and hooks all call the same one.

| item | value |
|---|---|
| Command | `just check` |
| Runs | format check, lint, types, spelling, dependency hygiene, tests with coverage, architecture rules, `just blueprint` (the stack list is in the stack file) |
| Passes when | exit 0; cross-file checks cover the whole repo, per-file linters the changed files, nothing else skipped |

## Changed files and the whole repo

Locally, a linter that judges one file at a time (formatter, per-file linter, shellcheck, spelling) runs on
the files changed against the base: committed on the branch, staged, unstaged, untracked and not ignored; never a
deleted one. A linter with nothing to look at is skipped and says so in one line. A change to a linter's own
config runs it over everything. A check that reads across files (types, architecture, dependencies) always
covers the whole repo, and so does `just check-all`. No base found means everything runs.

**Run `just check` while working; `just check-all` is rare.** `check` runs the tests the change reaches and skips any suite that already
passed on the same input, so a normal change takes seconds to a minute. `check-all` runs every test in every package with the coverage floor,
two minutes or more, and is the release gate: run it before a release tag. Do not run it per task, per
commit or per PR: it re-proves what `check` already proved.

`python -m any_gate changed` is the selector (`any-gate`, a dev dependency pinned by git tag; `--help` documents it). It prints the
changed files matching its globs, NUL-separated, or everything on `--scope all`, when a `--config` file changed, or with
no base. A repo adds a `-changed` twin of each per-file recipe and `check` calls the twins:

```just
lint-changed:
    #!/usr/bin/env bash
    set -euo pipefail
    list=$(mktemp); trap 'rm -f "$list"' EXIT
    uv run python -m any_gate changed --config pyproject.toml --config ruff.toml 'src/*.py' 'tests/*.py' > "$list"
    [ -s "$list" ] || { echo "skipped lint: no Python file changed"; exit 0; }
    xargs -0 uv run ruff check --force-exclude < "$list"
    xargs -0 uv run ruff format --check --force-exclude < "$list"
```

`spell-changed` is the same with `--config .codespellrc` and `xargs -0 uv run codespell < "$list"`. Keep the whole-repo
`lint` and `spell`; `check-all` calls those.

## The runner

The gate is a `justfile`, and `just` is the runner (shelf ADR 0023). Pin it per repo: Python `uv add --dev rust-just`,
run as `uv run just check`; other stacks `uvx rust-just@<version>` or brew. A gate that is only a
Makefile fails `gate.runner`. Three rules keep the file readable by blueprint, which dumps the graph with
`just --dump --dump-format json`:

- No backticks: `just --dry-run check` evaluates them, and blueprint dry-runs `check`. Put anything that needs a command's output inside a recipe body.
- Loops and multi-line shell go in a shebang recipe (`#!/usr/bin/env bash`, then `set -euo pipefail`); just has no loops.
- A dependency, or a recipe argument that names a recipe (`check: (steps "lint")`), is an edge in the graph.

## Generated files are current

A file a generator writes (a stylesheet, a schema, samples) is committed, so a change to its inputs must come with its regeneration. Declare
each generator in `pyproject.toml`; blueprint renders one `generated-<name>` step per entry, which runs the command into a temp folder and
compares:

```toml
[[tool.blueprint.gate.generated]]
name = "contract"
command = "uv run python scripts/contract.py --out {out}"   # {out}: a folder to write the outputs into, at their repo paths
outputs = ["contract"]                                      # files or folders
reads = ["src/*", "scripts/*"]                              # optional, fnmatch: what it reads; absent: the step runs on any change
```

A file that differs, is missing, or is left over (in an output folder, not generated) fails and names the fix: the same command with `{out}` as `.`.

## One box, many gates

Several agents share one machine, and each test run takes every core: on 2026-10-20 four gates at once on a 6-CPU box
took 11-14 min each instead of 2, and a push was killed. The shelf's `any-gate` package (a dev dependency, pinned by git
tag; `python -m any_gate --help` documents it) prevents both halves of that:

| piece | in the justfile | does |
|---|---|---|
| the test slot | the test command runs as `python -m any_lease run --root <dir> tests 1 <label> -- <command>`, or through `python -m any_gate test` | one test run per box at a time; a second gate waits and says who holds the slot. |
| the green record | `check` takes a first dependency running `python -m any_gate start`, and its body runs `python -m any_gate passed --gate check` | records the tree a green `check` saw, if no file changed during the run |
| the pre-push skip | the hook's entry is `uv run python -m any_gate pre-push --gate check -- uv run just check` | no second run when the working tree is clean and HEAD's tree is recorded; any doubt runs it |

Only the expensive step takes the slot, so the gate's parallel steps never wait on one another. `any-gate steps` (the `steps` recipe
runs it: `python -m any_gate steps --runner <just> <step>...`) points `GATE_NOTICE_FD` at its terminal, so the "waiting" line shows while the
step's own output goes to its log; it prints one timing line, marks a step over `GATE_STEP_BUDGET` (default 60 s) and the gate over
`GATE_BUDGET` (default 180 s), and prints the log of each failed step. The record keys on the tree and the upstream merge-base, and lives in the git directory every
worktree of the checkout shares: a rebase changes the key, and the gate runs again. A repo with no python runs `just check`
from the hook directly, with no skip.

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
| pre-push | `bd hooks run pre-push`, `bd sync` (pull, conflict check, push with retry; fatal, its exit code explained; `BD_DOLT_PUSH_OPTIONAL=1` to push offline; bare `bd dolt push` only as a fallback), then `just check` unless HEAD's tree already passed it | Heavy checks once per push, and not twice per tree |

After a clone, in this order, as plain commands (until `mise trust` every mise shim refuses, uv and just included):
`mise trust --yes && mise install --locked` (the exact tools mise.toml pins, from mise.lock; ADR 0024), the stack's sync
(python: `uv sync --locked`), `bd bootstrap` in a beads repo (its database comes from refs/dolt/data, not from git),
then `prek install`. A repo with LFS also needs `git lfs install --skip-repo` once per user. After a pin bump: `just tools`. Recipe: blueprint's `recipes/pre-commit-config.yaml`; bd hooks come first.

## Tool versions

Every tool that builds or tests the repo (uv, just, prek, bd, an engine editor) is pinned exactly in `mise.toml` and locked in
`mise.lock`; agent CLIs (codex, claude code, opencode, gemini) are never pinned (they update themselves per machine), and
a machine-owned tool such as git gets a minimum (`git = ">=2.40"`), not a pin; never install one with brew, apt or a curl script for this repo. A bump is a commit: edit the version, run
`mise lock`, commit both. `.python-version` (uv) and `global.json` (.NET) keep their own pins; mise does not pin them again.

## No CI

No repository has GitHub Actions CI (shelf ADR 0027). The gate runs locally: the pre-push hook and `just check` on the
machine that pushes are the only enforcement, so run `just check` before every push and never skip the hook. A
`.github/workflows` or `.github/actions` folder fails `gate.no-ci`: delete it. A duty a workflow carried that is not CI
(image publish, deploy, a scheduled eval) becomes a local command or waits for an owner decision; never keep a workflow to hold it.

## Exceptions

An exception to a blueprint rule (an override, an ignored path in `docs/blueprint/blueprint.toml`) carries a reason and
either `expires = <date>` or `adr = "NNNN"`, an accepted ADR in `docs/adr/` that records the durable decision. The gate
reports an exception with neither, or naming an ADR that is missing or not accepted.

## Adding a check

Plant a violation, see the gate fail, add the check to `just check` (a hook only if it takes seconds), remove the violation, see green.
