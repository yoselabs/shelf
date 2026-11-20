# Definition of Done: `just check` green over the WHOLE repo -- no carve-outs.
# "Pre-existing drift" / "unrelated file" never satisfies Done. (Inherited from a2kay AGENTS.md §1.)
#
# This is the reference toolchain every consumer of the shelf inherits (ADR 0004). The runner is
# just (ADR 0023): pinned per repo as the `rust-just` dev dependency, run as `uv run just <recipe>`.
#
# The gate's common recipes are the blueprint's, rendered into .blueprint/ (ADR 0029): `uv run blueprint render` rewrites them and
# `just render` fails on any difference. This file keeps only what is the shelf's own: a recipe defined here replaces the rendered one
# of the same name (`set allow-duplicate-recipes`). Consumers keep the same shape and own even less.
#
# No backticks anywhere in this file: `just --dry-run` evaluates them, and blueprint's
# gate.one-command dry-runs `check` and reads this graph from `just --dump --dump-format json`.
# Anything that needs a command's output lives inside a shebang recipe.

set shell := ["bash", "-euo", "pipefail", "-c"]
set allow-duplicate-recipes

import '.blueprint/base.just'
import '.blueprint/python.just'

# pytest runs one worker per core (pytest-xdist).
pytest_par := "-n auto"

# Where whole test runs queue (check-all's pytest below; `blueprint test` queues in the same folder): one slot, so gates started at once wait instead of thrashing.
lease_root := env_var_or_default("GATE_LEASE_ROOT", env_var_or_default("XDG_CACHE_HOME", env_var("HOME") + "/.cache") + "/gate-leases")

# The gate. Fast, deterministic tools first; tests last. Tests cover only what the change
# touches (`test`, the rendered `blueprint test`); `check-all` runs every test with the coverage floor: rare, before a release tag, never per task.
#
# The per-file linters (scripts, lint-changed, spell-changed) check only the files changed against the base
# in `check` (`any-gate changed`; a changed config file, or no base, selects everything). `check-all` runs them on every
# file (`scripts "all"`, `lint`, `spell`). The cross-file checks (typecheck, arch, deps, blueprint)
# always cover the whole repo. A linter with nothing changed prints "skipped <linter>: ..." and the gate
# repeats that line.
#
# A green `check` records the tree it checked (`any-gate`, `python -m any_gate start|passed|pre-push`): `gate-start` notes the
# working tree first, the body records it once every step passed and only if nothing changed meanwhile, and the
# pre-push hook then skips the gate for that exact tree.
[group('gate')]
check: gate-start beads-lint scripts (steps "guard" "preset" "render" "blueprint" "secrets" "lint-changed" "typecheck" "arch" "spell-changed" "deps" "test") check-extra
    uv run python -m any_gate passed --gate check

[group('gate')]
check-all: beads-lint (scripts "all") (steps "guard" "preset" "render" "blueprint" "secrets-all" "lint" "typecheck" "arch" "spell" "deps" "test-all")

# Every tracked shell script passes shellcheck (pinned in mise.toml), at its default severity. The name is the
# blueprint's for this step in every repo (stack/shell).
[group('gate')]
scripts scope="changed":
    #!/usr/bin/env bash
    set -euo pipefail
    command -v shellcheck >/dev/null || { echo "scripts: shellcheck is not installed -- run just tools" >&2; exit 2; }
    list=$(mktemp); trap 'rm -f "$list"' EXIT
    uv run python -m any_gate changed --scope {{ scope }} --config .shellcheckrc '*.sh' > "$list"
    [ -s "$list" ] || { echo "skipped scripts: no shell script changed"; exit 0; }
    xargs -0 shellcheck < "$list"

# One-time (idempotent, safe to re-run) setup for a CONSUMER repo: wires the commit guard,
# resolver block, beads (opt-out), and this linter preset via the operations in
# tools/onboard/ -- ordering and verification are enforced there (run_all()'s precondition
# harness), never re-implemented here as a recipe dependency graph. See
# docs/research/onboard-consumer-skill and docs/research/bootstrap-target-contract.
#
# Consumers copy this recipe the same way as `guard` above. Run inside the shelf's OWN repo,
# the underlying script refuses (there is nothing to onboard here -- this repo IS the shelf).
bootstrap:
    #!/usr/bin/env bash
    set -euo pipefail
    s=.agents/skills/onboard-consumer/scripts/onboard.py
    [ -f "$s" ] || s="${SHELF_HOME:-../shelf}/.agents/skills/onboard-consumer/scripts/onboard.py"
    [ -f "$s" ] || s="$HOME/Workspaces/shelf/.agents/skills/onboard-consumer/scripts/onboard.py"
    if [ -f "$s" ]; then python3 "$s" --repo .
    else echo "bootstrap: shelf clone not found (set SHELF_HOME) -- clone https://github.com/yoselabs/shelf" >&2; exit 2; fi

# Re-check this repo's onboarding state. NOT a `check` prerequisite -- an environment
# assertion, not a content one (bootstrap-target-contract design.md D4) -- and deliberately
# NOT read-only: the operations converge drift back to correct state on every call rather
# than merely reporting it (tools/onboard/verify.py's whole design). Mechanically identical
# to `bootstrap` above; the separate name signals intent to the caller.
bootstrap-verify: bootstrap

[group('gate')]
lint:
    uv run ruff check packages tests tools conftest.py
    uv run ruff format --check packages tests tools conftest.py

# `lint` over the files changed against the base (`any-gate changed`), for `check`. Shelf-only: consumers copy `lint`.
[group('gate')]
lint-changed:
    #!/usr/bin/env bash
    set -euo pipefail
    list=$(mktemp); trap 'rm -f "$list"' EXIT
    uv run python -m any_gate changed --config pyproject.toml --config ruff.toml 'packages/*.py' 'tests/*.py' 'tools/*.py' conftest.py > "$list"
    [ -s "$list" ] || { echo "skipped lint: no Python file changed"; exit 0; }
    xargs -0 uv run ruff check --force-exclude < "$list"
    xargs -0 uv run ruff format --check --force-exclude < "$list"

format:
    uv run ruff format packages tests tools conftest.py

# the import graph against the contracts in [tool.importlinter] (pyproject.toml): no package
# imports a consumer app, packages stay independent except their declared workspace edges.
# Banned APIs are ruff's TID251 and ride `lint`. A violation prints the importing line.
[group('gate')]
arch:
    uv run lint-imports

# typos in code, docstrings, and docs.
[group('gate')]
spell:
    uv run codespell packages tests tools docs catalog use-cases ledger README.md AGENTS.md CLAUDE.md conftest.py

# `spell` over the files changed against the base, for `check`. Shelf-only: consumers copy `spell`.
[group('gate')]
spell-changed:
    #!/usr/bin/env bash
    set -euo pipefail
    list=$(mktemp); trap 'rm -f "$list"' EXIT
    uv run python -m any_gate changed --config pyproject.toml --config .codespellrc 'packages/*' 'tests/*' 'tools/*' 'docs/*' 'catalog/*' 'use-cases/*' 'ledger/*' README.md AGENTS.md CLAUDE.md conftest.py > "$list"
    [ -s "$list" ] || { echo "skipped spell: no file changed"; exit 0; }
    xargs -0 uv run codespell < "$list"

# The test runs queue for one slot (`any-lease`, `lease_root` above): each takes every core, so gates started at once
# on one box wait instead of thrashing (2026-10-20: four at once took 11-14 min each).
#
# tests with coverage; the floor guards against REGRESSION (set just below current).
# Substrate adapters (docling/torch/subprocess) are legitimately hard to unit-test,
# so the floor is a rot-guard, not a vanity number. Raise it as coverage climbs.
[group('gate')]
test-all:
    uv run python -m any_lease run --root {{ lease_root }} tests 1 check-all -- uv run pytest {{ pytest_par }} --cov --cov-report=term-missing --cov-fail-under=65

# The real-launch browser gate (any-browser), deselected from the default `test`.
# Launches each real engine against a local JS page and asserts a render. CI runs
# this with SHELF_REQUIRE_BROWSER=1 (after installing Chromium: `patchright
# install --with-deps chromium`), where a non-launching engine is a hard FAILURE
# rather than a skip -- the one environment obligated to prove the browser starts.
# The trailing `-m browser` overrides the pyproject `-m "not browser"` default.
test-browser:
    uv run pytest packages/any-browser/tests -m browser -p no:cacheprovider

# The skills' eval cases (evals/<skill>/<case>/), with `claude plugin eval`. Not in `check`: live
# runs cost money. Run from a copy without .venv and .git: plugin eval refuses a plugin dir of
# more than 20000 entries. Extra flags pass through: `just eval --case 'audit-*'`.
eval *args:
    #!/usr/bin/env bash
    set -uo pipefail
    d=$(mktemp -d)
    rsync -a --exclude .venv --exclude .git --exclude __pycache__ --exclude '.*_cache' --exclude .hypothesis \
        --exclude .beads --exclude evals/results --exclude .worktrees --exclude .claude/worktrees ./ "$d/" && \
    ( cd "$d" && claude plugin eval . --trust-plugin --scaffold --allow-tools Bash Write Edit --max-cost-usd 20 {{ args }} )
    rc=$?
    mkdir -p evals/results && cp -R "$d/evals/results/." evals/results/ 2>/dev/null
    rm -rf "$d"
    exit $rc

# regenerate the derived ontology indexes (catalog/ledger/use-cases READMEs).
# The files are truth; the READMEs are projected (constitution I). A freshness
# test in `just test` fails if they drift.
catalog:
    uv run python tools/catalog.py
