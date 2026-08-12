# Definition of Done: `make check` green over the WHOLE repo — no carve-outs.
# "Pre-existing drift" / "unrelated file" never satisfies Done. (Inherited from a2kay AGENTS.md §1.)
#
# This is the reference toolchain every consumer of the shelf inherits (resolution 0004).
# Each target is one linter doing one job; `check` is the gate.

.PHONY: check guard bootstrap bootstrap-verify lint format typecheck spell deps test test-browser cov catalog advisory sync

# The gate. Fast, deterministic tools first; tests last.
check: guard lint typecheck spell deps test

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
# Consumers copy this target verbatim -- it finds the guard in-repo (the shelf) or
# via $SHELF_HOME -> ../shelf -> ~/Workspaces/shelf (a consumer). Exit 2 means the
# guard could not run, which is never treated as a pass.
guard:
	@g=tools/hooks/forbid-local-shelf-source.py; \
	 [ -f "$$g" ] || g="$${SHELF_HOME:-../shelf}/tools/hooks/forbid-local-shelf-source.py"; \
	 [ -f "$$g" ] || g="$$HOME/Workspaces/shelf/tools/hooks/forbid-local-shelf-source.py"; \
	 if [ -f "$$g" ]; then python3 "$$g" --committed; \
	 else echo "guard: shelf clone not found (set SHELF_HOME) -- CANNOT VERIFY, not a pass" >&2; exit 2; fi

# One-time (idempotent, safe to re-run) setup for a CONSUMER repo: wires the commit guard,
# resolver block, beads (opt-out), and this linter preset via the operations in
# tools/onboard/ -- ordering and verification are enforced there (run_all()'s precondition
# harness), never re-implemented here as a Make prerequisite graph. See
# openspec/changes/onboard-consumer-skill and openspec/changes/bootstrap-target-contract.
#
# Consumers copy this target the same way as `guard` above. Run inside the shelf's OWN repo,
# the underlying script refuses (there is nothing to onboard here -- this repo IS the shelf).
bootstrap:
	@s=.agents/skills/onboard-consumer/scripts/onboard.py; \
	 [ -f "$$s" ] || s="$${SHELF_HOME:-../shelf}/.agents/skills/onboard-consumer/scripts/onboard.py"; \
	 [ -f "$$s" ] || s="$$HOME/Workspaces/shelf/.agents/skills/onboard-consumer/scripts/onboard.py"; \
	 if [ -f "$$s" ]; then python3 "$$s" --repo .; \
	 else echo "bootstrap: shelf clone not found (set SHELF_HOME) -- clone https://github.com/yoselabs/shelf" >&2; exit 2; fi

# Re-check this repo's onboarding state. NOT a `check` prerequisite -- an environment
# assertion, not a content one (bootstrap-target-contract design.md D4) -- and deliberately
# NOT read-only: the operations converge drift back to correct state on every call rather
# than merely reporting it (tools/onboard/verify.py's whole design). Mechanically identical
# to `bootstrap` above; the separate name signals intent to the caller.
bootstrap-verify: bootstrap

lint:
	uv run ruff check packages tests tools conftest.py
	uv run ruff format --check packages tests tools conftest.py

format:
	uv run ruff format packages tests tools conftest.py

# --error-on-warning: a type warning fails the build. No slow rot.
typecheck:
	uv run ty check --error-on-warning packages

# typos in code, docstrings, and docs.
spell:
	uv run codespell packages tests tools docs catalog use-cases ledger README.md AGENTS.md CLAUDE.md conftest.py

# dependency hygiene per package (unused / missing / transitive). deptry reads each
# package's own pyproject from its dir; --known-first-party (the src import name)
# silences the src-layout self-import DEP003 noise.
deps:
	@for p in packages/*/; do \
	  imp=$$(ls "$$p/src"); \
	  echo "-- deptry $$p (first-party: $$imp)"; \
	  ( cd "$$p" && uv run deptry . --known-first-party "$$imp" ) || exit 1; \
	done

# tests with coverage; the floor guards against REGRESSION (set just below current).
# Substrate adapters (docling/torch/subprocess) are legitimately hard to unit-test,
# so the floor is a rot-guard, not a vanity number. Raise it as coverage climbs.
test:
	uv run pytest --cov --cov-report=term-missing --cov-fail-under=65

# The real-launch browser gate (any-browser), deselected from the default `test`.
# Launches each real engine against a local JS page and asserts a render. CI runs
# this with SHELF_REQUIRE_BROWSER=1 (after installing Chromium: `patchright
# install --with-deps chromium`), where a non-launching engine is a hard FAILURE
# rather than a skip — the one environment obligated to prove the browser starts.
# The trailing `-m browser` overrides the pyproject `-m "not browser"` default.
test-browser:
	uv run pytest packages/any-browser/tests -m browser -p no:cacheprovider

# coverage report only (human view).
cov:
	uv run pytest --cov --cov-report=term-missing

# regenerate the derived ontology indexes (catalog/ledger/use-cases READMEs).
# The files are truth; the READMEs are projected (constitution I). A freshness
# test in `make test` fails if they drift.
catalog:
	uv run python tools/catalog.py

# cross-package duplication / name-collision signals (T0-primitive candidates).
# NON-blocking on purpose — constitution VI values some duplication. Not in `check`.
advisory:
	uv run python tools/arch_advisory.py

sync:
	uv sync
