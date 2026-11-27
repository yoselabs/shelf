# Rendered by `blueprint gate render` -- never edit; a recipe of the same name in the repo's justfile replaces it only through a declared override (gate.recipe-shadowing).
# The python+uv stack: its linter (ruff and codespell), type, dependency and test steps.

# Paths and extra steps are data in pyproject.toml `[tool.blueprint.gate]` (blueprint gate --help): a repo defines no recipe of its own.
[group('gate')]
lint:
    uv run blueprint gate lint

# `lint` (ruff, then codespell) over the files changed against the base (any-gate changed), for `check`; `lint` itself is the whole repo.
[group('gate')]
lint-changed:
    uv run blueprint gate lint --changed

format:
    uv run blueprint gate format

# A type warning fails the build (pyrefly's config). No slow rot.
[group('gate')]
typecheck:
    uv run pyrefly check

# Typos in code, docstrings and docs (`lint` runs this too; here it is alone).
[group('gate')]
spell:
    uv run blueprint gate spell

# `spell` alone over the files changed against the base (`lint-changed` runs it too).
[group('gate')]
spell-changed:
    uv run blueprint gate spell --changed

# Dependency hygiene: the lockfile matches pyproject, then unused, missing and transitive (deptry), once per package in a workspace.
[group('gate')]
deps:
    #!/usr/bin/env bash
    set -euo pipefail
    env -u UV_FROZEN uv lock --check
    if [ -d packages ]; then
        printf '%s\0' packages/*/ | xargs -0 -P "$(getconf _NPROCESSORS_ONLN)" -I{} bash -c \
            'p={}; imp=$(ls "$p/src"); out=$(cd "$p" && uv run deptry . --known-first-party "$imp" 2>&1) || { printf -- "-- deptry %s\n%s\n" "$p" "$out"; exit 1; }'
    else
        uv run deptry .
    fi

# The tests the change reaches, through any-gate (`blueprint gate test`): suites that already passed on this input are skipped, the rest
# queue for one test slot. Declared test units combine cached coverage before enforcing their whole-repo floor. With
# `[tool.blueprint.test] marks = "not slow"` a suite's `slow` tests run in a second pass, only when that suite's key changed since they last
# passed (a docs-only change runs none). Arguments go to pytest: `just test -m slow`, `just test -k name`.
# A run with arguments is an override: it writes no receipt, so a later plain run cannot skip a unit this one never ran in full.
[group('gate')]
[positional-arguments]
test *args:
    uv run blueprint gate test -- "$@"

# `test` over every suite and every mark, receipts ignored (the release gate's test step): the same runner, plan and test slot. A coverage
# floor applies only when the repo declares one (`[tool.blueprint.test] floor`, else `[tool.coverage.report] fail_under`); a whole-repo
# measure cannot ride on a partial run, so with arguments (`just test-all -m slow`) the floor is off.
[group('gate')]
[positional-arguments]
test-all *args:
    uv run blueprint gate test-all -- "$@"

# Coverage report only (human view).
cov:
    uv run pytest --cov --cov-report=term-missing

sync:
    uv sync

# The import graph against the contracts in [tool.importlinter] (pyproject.toml) or `.importlinter`. A violation prints the importing line.
# Rendered only when the repo declares contracts: the node twin of this slot is `ui-arch` (dependency-cruiser).
[group('gate')]
arch:
    uv run lint-imports
