# The import graph against the contracts in [tool.importlinter] (pyproject.toml) or `.importlinter`. A violation prints the importing line.
# Rendered only when the repo declares contracts: the node twin of this slot is `ui-arch` (dependency-cruiser).
[working-directory('@PY@')]
[group('gate')]
arch:
    uv run lint-imports
