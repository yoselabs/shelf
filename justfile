# Definition of Done: `just check` green over the WHOLE repo -- no carve-outs.
# "Pre-existing drift" / "unrelated file" never satisfies Done. (Inherited from a2kay AGENTS.md §1.)
#
# This is the reference toolchain every consumer of the shelf inherits (ADR 0004). The runner is
# just (ADR 0023): pinned per repo as the `rust-just` dev dependency, run as `uv run just <recipe>`.
# Each recipe is one linter doing one job; `check` is the gate.
#
# No backticks anywhere in this file: `just --dry-run` evaluates them, and blueprint's
# gate.one-command dry-runs `check` and reads this graph from `just --dump --dump-format json`.
# Anything that needs a command's output lives inside a shebang recipe.

set shell := ["bash", "-euo", "pipefail", "-c"]

# pytest runs one worker per core (pytest-xdist).
pytest_par := "-n auto"

# One image per checkout, so worktrees never run each other's code. Image: tools/gate/gate.Dockerfile.
test_image := "shelf-gate-" + file_name(justfile_directory())

# The gate. Fast, deterministic tools first; tests last. Tests cover only what the change
# touches (`test-affected`); `check-all` runs every test with the coverage floor, and CI runs
# `check-all`.
#
# Both run inside a Linux container when Docker answers: on the macOS host an endpoint scanner
# inspects every process start and file write, and the suite took 10-17 min there (2026-10-10).
# In CI, inside a container, or with SHELF_HOST_CHECK=1 they run in place; the container
# speeds the gate up and is never required.
[group('gate')]
check: beads-lint secrets images (gate "check-host")

[group('gate')]
check-all: beads-lint secrets images (gate "check-all-host")

# Every bead still to be started (open or blocked) carries its acceptance criteria: criteria are what make a bead
# ready (owner, 2026-10-10); claimed work is past that gate and a deferred idea may stay unfinished. Runs on the
# host, before the container: bd's database lives in this clone (CI bootstraps it from refs/dolt/data first).
[group('gate')]
beads-lint:
    #!/usr/bin/env bash
    set -euo pipefail
    [ -d .beads ] || exit 0
    command -v bd >/dev/null || { echo "beads-lint: bd is not installed -- run just tools" >&2; exit 2; }
    # A clone with no (or an uninitialized) database lints 0 beads and exits 0; that is no pass (shelf-9g7).
    if ! out=$(BD_DISABLE_METRICS=1 bd list --limit 1 --json 2>&1); then
        echo "beads-lint: bd's database does not answer in this clone -- run bd bootstrap" >&2
        case "$out" in *"not initialized"*) echo "  (bootstrap calls an uninitialized one 'nothing to do': mv .beads/embeddeddolt .beads/embeddeddolt.broken first)" >&2;; esac
        exit 1
    fi
    rc=0
    for status in open blocked; do BD_DISABLE_METRICS=1 bd lint --status "$status" || rc=1; done
    exit "$rc"

# No secret in the history (gitleaks, pinned in mise.toml; about a second). A false positive goes in .gitleaks.toml
# with a description saying why. Runs on the host, before the container, beside beads-lint: the image has no gitleaks.
[group('gate')]
secrets:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v gitleaks >/dev/null || { echo "secrets: gitleaks is not installed -- run just tools" >&2; exit 2; }
    gitleaks git --no-banner --redact --log-level warn .

# Every Dockerfile passes hadolint (pinned in mise.toml; each ignored rule's reason is in .hadolint.yaml). On the host,
# beside secrets: the image has no hadolint.
[group('gate')]
images:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v hadolint >/dev/null || { echo "images: hadolint is not installed -- run just tools" >&2; exit 2; }
    git ls-files -z '*Dockerfile' '*Dockerfile.*' '*Containerfile' | grep -zv '\.dockerignore$' | xargs -0 -r hadolint

# The dispatch sits in its own private recipe so `check` and `check-all` stay plain dependency edges
# for the graph reader.
[private]
gate target:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -z "${CI:-}" ] && [ -z "${SHELF_HOST_CHECK:-}" ] && [ ! -f /.dockerenv ] && docker info >/dev/null 2>&1; then
        {{ just_executable() }} container {{ target }}
    else
        {{ just_executable() }} {{ target }}
    fi

[group('gate')]
check-host: (steps "guard" "preset" "blueprint" "lint" "typecheck" "arch" "spell" "deps" "test-affected")

[group('gate')]
check-all-host: (steps "guard" "preset" "blueprint" "lint" "typecheck" "arch" "spell" "deps" "test")

# Runs the gate's steps at once, each into its own log, then prints one timing line (a step over its budget is
# marked) and the log of every step that failed. Each name is a recipe, so the gate graph still reads the edges.
# Budgets, in seconds: GATE_STEP_BUDGET (default 60) per step, GATE_BUDGET (default 180) for the whole gate. The
# gate runs several times within one feature, so a slow step is a cost to see and fix, not to wait out.
[private]
steps +names:
    #!/usr/bin/env bash
    set -uo pipefail
    step_budget=${GATE_STEP_BUDGET:-60}; gate_budget=${GATE_BUDGET:-180}
    dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
    SECONDS=0
    echo "gate: {{ names }} (in parallel)" >&2
    for n in {{ names }}; do
        ( SECONDS=0; {{ just_executable() }} "$n" > "$dir/$n.log" 2>&1; echo "$? $SECONDS" > "$dir/$n.rc" ) &
    done
    wait
    total=$SECONDS; failed=(); line=()
    for n in {{ names }}; do
        read -r rc took < "$dir/$n.rc"
        mark=""; [ "$took" -gt $step_budget ] && mark=" ⚠ over ${step_budget}s"
        [ "$rc" -eq 0 ] || { failed+=("$n"); mark="$mark ✗"; }
        line+=("$n ${took}s$mark")
    done
    for n in "${failed[@]}"; do echo "--- $n" >&2; cat "$dir/$n.log" >&2; done
    summary=$(printf '%s · ' "${line[@]}"); echo "gate: ${summary% · } -- total ${total}s" >&2
    [ "$total" -gt $gate_budget ] && echo "gate: ⚠ ${total}s is over the ${gate_budget}s gate budget: find the slow step above" >&2
    [ "${#failed[@]}" -eq 0 ] || { echo "gate: failed: ${failed[*]}" >&2; exit 1; }

test-image:
    docker build -q -f tools/gate/gate.Dockerfile -t {{ test_image }} .

# In a git worktree `.git` is a file pointing into the main checkout's .git; the image holds only
# that pointer, so the main .git is mounted read-only at its own path and git skips optional locks.
# The result cache lives in a named volume per checkout, so it survives between container runs.
container target: test-image
    #!/usr/bin/env bash
    set -euo pipefail
    mounts=()
    if [ ! -e .git/HEAD ]; then
        common="$(git rev-parse --path-format=absolute --git-common-dir)"
        mounts=(-v "$common:$common:ro" -e GIT_OPTIONAL_LOCKS=0)
    fi
    docker run --rm "${mounts[@]}" -v {{ test_image }}-cache:/app/.cache {{ test_image }} just {{ target }}

# The blueprint's per-commit checkpoints (packages/blueprint): one line per one that is not
# passing. The audit-only ones (slow, or reading this clone's bd database) run in the
# /blueprint audit, not here. Same resolution order as `guard`.
[group('gate')]
blueprint:
    #!/usr/bin/env bash
    set -euo pipefail
    s=packages/blueprint/src
    [ -d "$s/blueprint" ] || s="${SHELF_HOME:-../shelf}/packages/blueprint/src"
    [ -d "$s/blueprint" ] || s="$HOME/Workspaces/shelf/packages/blueprint/src"
    if [ -d "$s/blueprint" ]; then PYTHONPATH="$s" python3 -m blueprint check --repo . --gate
    else echo "blueprint: shelf clone not found (set SHELF_HOME) -- CANNOT VERIFY, not a pass" >&2; exit 2; fi

# The commit guard as a GATE, not only a hook. A pre-commit hook is per-clone and
# can be silently disabled by anything that claims core.hooksPath -- beads, husky,
# lefthook -- which happened in this very repo and went unnoticed because the hook
# file still existed and looked installed. So the hook is FAST FEEDBACK and this is
# the ENFORCEMENT: it needs no onboarding, no hooks, and holds on any fresh clone.
#
# --committed reads HEAD, deliberately not the working tree: an *uncommitted* local
# override is the supported co-development workflow (docs/consuming-the-shelf.md
# §1), and a gate that failed on it would break the thing the docs prescribe.
#
# Consumers copy this recipe verbatim -- it finds the guard in-repo (the shelf) or
# via $SHELF_HOME -> ../shelf -> ~/Workspaces/shelf (a consumer). Exit 2 means the
# guard could not run, which is never treated as a pass.
[group('gate')]
guard:
    #!/usr/bin/env bash
    set -euo pipefail
    g=tools/hooks/forbid-local-shelf-source.py
    [ -f "$g" ] || g="${SHELF_HOME:-../shelf}/tools/hooks/forbid-local-shelf-source.py"
    [ -f "$g" ] || g="$HOME/Workspaces/shelf/tools/hooks/forbid-local-shelf-source.py"
    if [ -f "$g" ]; then python3 "$g" --committed
    else echo "guard: shelf clone not found (set SHELF_HOME) -- CANNOT VERIFY, not a pass" >&2; exit 2; fi

# The linter preset, as a GATE. ADR 0004 makes this repo's config the preset and
# says drift is "acceptable and visible" -- it was not visible. The onboarding copy is
# append-only, so it reports "already current" for a repo missing whole rule families.
# This fails on any difference from the preset that the consumer has not declared, with
# a reason, in its own [tool.shelf-preset]. Inside the shelf it is a no-op: this repo IS
# the preset, so there is nothing to compare against.
#
# Consumers copy this recipe verbatim, same resolution order as `guard`.
[group('gate')]
preset:
    #!/usr/bin/env bash
    set -euo pipefail
    g=tools/preset_drift.py
    [ -f "$g" ] || g="${SHELF_HOME:-../shelf}/tools/preset_drift.py"
    [ -f "$g" ] || g="$HOME/Workspaces/shelf/tools/preset_drift.py"
    if [ -f "$g" ]; then python3 "$g" --repo .
    else echo "preset: shelf clone not found (set SHELF_HOME) -- CANNOT VERIFY, not a pass" >&2; exit 2; fi

# The pinned tools (mise.toml, locked by mise.lock; ADR 0024). The user's own config is left out: its
# unlocked tools (`latest`) would make `--locked` refuse the whole install.
tools:
    mise trust --yes .
    MISE_IGNORED_CONFIG_PATHS="$HOME/.config/mise" mise install --locked

# One-time (idempotent, safe to re-run) setup for a CONSUMER repo: wires the commit guard,
# resolver block, beads (opt-out), and this linter preset via the operations in
# tools/onboard/ -- ordering and verification are enforced there (run_all()'s precondition
# harness), never re-implemented here as a recipe dependency graph. See
# openspec/changes/onboard-consumer-skill and openspec/changes/bootstrap-target-contract.
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

format:
    uv run ruff format packages tests tools conftest.py

# A type warning fails the build (pyrefly's config). No slow rot.
[group('gate')]
typecheck:
    uv run pyrefly check

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

# dependency hygiene: uv.lock matches every pyproject (`uv run` alone never notices a stale lock;
# shelf main ran green on one, 2026-10-11), then per package (unused / missing / transitive). deptry reads each
# package's own pyproject from its dir; --known-first-party (the src import name)
# silences the src-layout self-import DEP003 noise. A shebang recipe: just has no loops.
[group('gate')]
deps:
    #!/usr/bin/env bash
    set -euo pipefail
    env -u UV_FROZEN uv lock --check
    # One deptry per package, all cores at once; a package's output prints only when it fails.
    printf '%s\n' packages/*/ | xargs -P "$(getconf _NPROCESSORS_ONLN)" -I{} bash -c \
        'p={}; imp=$(ls "$p/src"); out=$(cd "$p" && uv run deptry . --known-first-party "$imp" 2>&1) || { printf -- "-- deptry %s\n%s\n" "$p" "$out"; exit 1; }'
    echo "deptry: every package clean"

# tests with coverage; the floor guards against REGRESSION (set just below current).
# Substrate adapters (docling/torch/subprocess) are legitimately hard to unit-test,
# so the floor is a rot-guard, not a vanity number. Raise it as coverage climbs.
[group('gate')]
test:
    uv run pytest {{ pytest_par }} --cov --cov-report=term-missing --cov-fail-under=65

# Only the tests a change can reach: the changed packages, every package depending on them,
# and the fitness tests (tools/affected.py). A package whose inputs are unchanged since its suite
# last passed is skipped (the result cache, .cache/affected-passed.json). No coverage floor: it is
# measured over the whole repo, so a partial run cannot meet it.
[group('gate')]
test-affected:
    #!/usr/bin/env bash
    set -euo pipefail
    paths="$(python3 tools/affected.py --explain --skip-passed)"
    uv run pytest {{ pytest_par }} -p no:cov $paths && python3 tools/affected.py --record $paths

# The real-launch browser gate (any-browser), deselected from the default `test`.
# Launches each real engine against a local JS page and asserts a render. CI runs
# this with SHELF_REQUIRE_BROWSER=1 (after installing Chromium: `patchright
# install --with-deps chromium`), where a non-launching engine is a hard FAILURE
# rather than a skip -- the one environment obligated to prove the browser starts.
# The trailing `-m browser` overrides the pyproject `-m "not browser"` default.
test-browser:
    uv run pytest packages/any-browser/tests -m browser -p no:cacheprovider

# coverage report only (human view).
cov:
    uv run pytest --cov --cov-report=term-missing

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

# cross-package duplication / name-collision signals (T0-primitive candidates).
# NON-blocking on purpose -- constitution VI values some duplication. Not in `check`.
advisory:
    uv run python tools/arch_advisory.py

sync:
    uv sync
