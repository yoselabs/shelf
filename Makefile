# Definition of Done: `make check` green over the WHOLE repo — no carve-outs.
# "Pre-existing drift" / "unrelated file" never satisfies Done. (Inherited from a2kay AGENTS.md §1.)

.PHONY: check lint format typecheck test sync

check: lint typecheck test

lint:
	uv run ruff check packages tests
	uv run ruff format --check packages tests

format:
	uv run ruff format packages tests

typecheck:
	uv run ty check packages

test:
	uv run pytest

sync:
	uv sync
