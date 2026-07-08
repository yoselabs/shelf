# sqlite-resource

**Stop caring about aiosqlite's open/close plumbing.** A lazily-opened connection with
an internal lock, an idempotent close, and the async context-manager protocol — so the
app holds a resource and reads `.conn`, never the double-checked lazy-open dance.

```python
from pathlib import Path
from sqlite_resource import SqliteResource

async def apply_schema(conn):
    await conn.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)")

res = SqliteResource(Path("~/.app/data.sqlite").expanduser(), on_open=apply_schema)

async with res:                       # opens once, applies pragmas + on_open
    await res.conn.execute("INSERT INTO kv VALUES ('a', '1')")
    await res.conn.commit()
# closed on exit; re-entering re-opens
```

- **Lazy** — no I/O until the first `ensure()` / `async with`. A process that never
  touches the DB never opens a connection.
- **Safe under races** — concurrent first-callers serialize on an internal lock;
  double-open and double-close are no-ops.
- **Domain-free** — schema and pragmas are caller-supplied (`on_open`, `pragmas`), so
  the primitive knows how to *manage a connection*, not what lives in it.

## Surface

- `SqliteResource(db_path, *, pragmas=("journal_mode=WAL",), on_open=None)`
- `await res.ensure() -> aiosqlite.Connection` — open on first call, idempotent
- `res.conn` — the open connection (raises if accessed before `ensure()`)
- `await res.close()` — idempotent
- `async with res:` — opens eagerly on enter, closes on exit
