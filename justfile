# Definition of Done: `just check` green over the WHOLE repo -- no carve-outs.
# "Pre-existing drift" / "unrelated file" never satisfies Done. (Inherited from a2kay AGENTS.md §1.)
#
# This is the reference toolchain every consumer of the shelf inherits (ADR 0004). The runner is
# just (ADR 0023): pinned per repo as the `rust-just` dev dependency, run as `uv run just <recipe>`.
#
# The gate's common recipes are the blueprint's, rendered into .blueprint/ (ADR 0029): `uv run blueprint gate render` rewrites them and
# `just render` fails on any difference. This file keeps only what is the shelf's own, and redefines none of the rendered recipes
# (gate.recipe-shadowing): paths and extra steps are data in pyproject.toml `[tool.blueprint.gate]`. Consumers keep the same shape.
#
# No backticks anywhere in this file: `just --dry-run` evaluates them, and blueprint's
# gate.one-command dry-runs `check` and reads this graph from `just --dump --dump-format json`.
# Anything that needs a command's output lives inside a shebang recipe.

set shell := ["bash", "-euo", "pipefail", "-c"]
set allow-duplicate-recipes

import '.blueprint/base.just'
import '.blueprint/python.just'

# The decision records are the shelf's own to keep (any-knowledge); blueprint does not check them. Runs after the steps, before the record.
[private]
check-extra: adr-check

[group('gate')]
adr-check:
    uv run python -m any_knowledge check

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

# Every package version on origin/main has its `<name>-v<version>` tag (2026-11-09: anyllm 0.8.0 was merged and never tagged, so a consumer
# could not pin it). A release is bump, merge, tag, so the next gate after an untagged merge is the one that stops. Offline it reads local tags.
# The release gate's form of `scripts`: every tracked shell script, not only the changed ones.
[group('gate')]
scripts-all: (scripts "all")

# No locked dependency has a known vulnerability, except those .config/dep-audit/exceptions.toml allows until a date. `check` runs it when uv.lock or
# a pyproject.toml changed (gate-inputs.toml); `check-all` always. Needs the network: offline it says so and passes.
[group('gate')]
dep-audit:
    python3 -I tools/dep_audit/dep_audit.py

[group('gate')]
tag-check:
    python3 -I tools/tag_check/tag_check.py

# No tracked `*.py` file or package folder is named like a standard library module where a script run puts it first on sys.path (a consumer's
# `queue.py` in scripts/ broke 729 jobs, 2026-11: `module 'queue' has no attribute 'SimpleQueue'`). Reasoned exceptions: .config/stdlib-shadow/allow.toml.
# Its inputs: the Python files (a step of the repo's own, so gate-inputs.toml declares it).
[group('gate')]
stdlib-shadow:
    python3 -I tools/stdlib_shadow/stdlib_shadow.py

# The real-launch browser gate (any-browser), deselected from the default `test`.
# Launches each real engine against a local JS page and asserts a render. Run
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
    uv run python tools/catalog/catalog.py
