# Definition of Done: `make check` green over the WHOLE repo — no carve-outs.
# "Pre-existing drift" / "unrelated file" never satisfies Done. (Inherited from a2kay AGENTS.md §1.)
#
# This is the reference toolchain every consumer of the shelf inherits (resolution 0004).
# Each target is one linter doing one job; `check` is the gate.

.PHONY: check lint format typecheck spell deps test cov sync

# The gate. Fast, deterministic tools first; tests last.
check: lint typecheck spell deps test

lint:
	uv run ruff check packages tests
	uv run ruff format --check packages tests

format:
	uv run ruff format packages tests

# --error-on-warning: a type warning fails the build. No slow rot.
typecheck:
	uv run ty check --error-on-warning packages

# typos in code, docstrings, and docs.
spell:
	uv run codespell packages tests docs README.md AGENTS.md CLAUDE.md

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

# coverage report only (human view).
cov:
	uv run pytest --cov --cov-report=term-missing

sync:
	uv sync
