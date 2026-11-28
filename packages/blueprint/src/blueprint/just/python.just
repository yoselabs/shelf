# Rendered by `blueprint gate render` -- never edit; a recipe of the same name in the repo's justfile replaces it only through a declared override (gate.recipe-shadowing).
# The python+uv stack: its linter (ruff and codespell), type, dependency and test steps.

# Paths and extra steps are data in pyproject.toml `[tool.blueprint.gate]` (blueprint gate --help): a repo defines no recipe of its own.
[working-directory('@PY@')]
[group('gate')]
lint:
    uv run blueprint gate lint

# `lint` (ruff, then codespell) over the files changed against the base (any-gate changed), for `check`; `lint` itself is the whole repo.
[working-directory('@PY@')]
[group('gate')]
lint-changed:
    uv run blueprint gate lint --changed

[working-directory('@PY@')]
format:
    uv run blueprint gate format

# A type warning fails the build (pyrefly's config). No slow rot.
[working-directory('@PY@')]
[group('gate')]
typecheck:
    uv run pyrefly check

# Typos in code, docstrings and docs (`lint` runs this too; here it is alone).
[working-directory('@PY@')]
[group('gate')]
spell:
    uv run blueprint gate spell

# `spell` alone over the files changed against the base (`lint-changed` runs it too).
[working-directory('@PY@')]
[group('gate')]
spell-changed:
    uv run blueprint gate spell --changed

# Dependency hygiene: the lockfile matches pyproject, then unused, missing and transitive (deptry), once per package in a workspace. A
# package is checked when the change reaches it: its own files, a package it depends on (a dependency's modules and requirements decide what
# deptry calls missing or transitive), or the lock read per package (`any_gate_python packages`); where that adapter is absent, every package.
[working-directory('@PY@')]
[group('gate')]
deps scope="changed":
    #!/usr/bin/env bash
    set -euo pipefail
    env -u UV_FROZEN uv lock --check
    if [ -d packages ]; then
        every=$(cd packages && printf '%s\n' */ | tr -d /)
        if [ "{{ scope }}" = all ]; then pkgs=$every; else pkgs=$(uv run python -m any_gate_python packages 2>/dev/null) || pkgs=$every; fi
        [ -n "$pkgs" ] || { echo "skipped deps: no package reached"; exit 0; }
        echo "gate-note: $(echo $pkgs | wc -w | tr -d ' ')/$(echo $every | wc -w | tr -d ' ') packages"
        printf 'packages/%s/\0' $pkgs | xargs -0 -P "$(getconf _NPROCESSORS_ONLN)" -I{} bash -c \
            'p={}; imp=$(ls "$p/src"); out=$(cd "$p" && uv run deptry . --known-first-party "$imp" 2>&1) || { printf -- "-- deptry %s\n%s\n" "$p" "$out"; exit 1; }'
    else
        uv run deptry .
    fi

# The release gate's form of `deps`: every package, not only the ones the change reaches.
[group('gate')]
deps-all: (deps "all")

# The tests the change reaches, through any-gate (`blueprint gate test`): suites that already passed on this input are skipped, the rest
# queue for one test slot. Declared test units combine cached coverage before enforcing their whole-repo floor. With
# `[tool.blueprint.test] marks = "not slow"` a suite's `slow` tests run in a second pass, only when that suite's key changed since they last
# passed (a docs-only change runs none). Arguments go to pytest: `just test -m slow`, `just test -k name`.
# A run with arguments is an override: it writes no receipt, so a later plain run cannot skip a unit this one never ran in full.
[working-directory('@PY@')]
[group('gate')]
[positional-arguments]
test *args:
    uv run blueprint gate test -- "$@"

# `test` over every suite and every mark, receipts ignored (the release gate's test step): the same runner, plan and test slot. A coverage
# floor applies only when the repo declares one (`[tool.blueprint.test] floor`, else `[tool.coverage.report] fail_under`); a whole-repo
# measure cannot ride on a partial run, so with arguments (`just test-all -m slow`) the floor is off.
[working-directory('@PY@')]
[group('gate')]
[positional-arguments]
test-all *args:
    uv run blueprint gate test-all -- "$@"

# Coverage report only (human view).
[working-directory('@PY@')]
cov:
    uv run pytest --cov --cov-report=term-missing

[working-directory('@PY@')]
sync:
    uv sync
