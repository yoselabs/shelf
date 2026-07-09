"""DuckDB sidecar connect — normalize the target, create the parent dir, connect.

A sidecar store (graph, audit, search, job history, or any other per-concern
derived-state file) opens its single writer connection the same way every time:
normalize the target, create the parent directory for a file target, support the
``":memory:"`` passthrough, then ``duckdb.connect``. This module is the one place
that dance lives.

Connection acquisition only — each store keeps its own schema, migrations, and
query surface.
"""

from __future__ import annotations

from pathlib import Path

import duckdb


def connect(path: Path | str) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection for a sidecar store.

    For a file target, create the parent directory (``parents=True,
    exist_ok=True``) so a store can be opened under a not-yet-created subtree. The
    ``":memory:"`` target opens an in-memory connection and touches no filesystem
    path.
    """
    target = str(path)
    if target != ":memory:":
        target = str(Path(path))
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(target)


__all__ = ["connect"]
