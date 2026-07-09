# duckdb-sidecar

**Stop repeating the DuckDB sidecar-connection dance.** Per-concern derived-state
stores (a graph store, an audit log, a search index, job history — anything that
owns a single writer connection to its own DuckDB file) all open that connection
the same way: normalize the target, create the parent directory for a file target,
support the `":memory:"` passthrough, then `duckdb.connect`. This is the one place
that dance lives.

```python
from pathlib import Path
from duckdb_sidecar import connect

conn = connect(Path("vault/.derived/graph.duckdb"))
conn = connect(":memory:")  # in-memory, touches no filesystem path
```

Connection acquisition only — each store keeps its own schema, migrations, and
query surface. Deliberately not a lifecycle base class.

## Boundary

Imports no consumer app (`a2web`, `a2kay`) — enforced by `tests/test_boundary_duckdb_sidecar.py`.
