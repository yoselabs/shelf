"""DuckDB sidecar helpers — open the connection, and survive the two hazards.

A sidecar store (graph, audit, search, job history, or any other per-concern
derived-state file) opens its single writer connection the same way every time:
normalize the target, create the parent directory for a file target, support the
``":memory:"`` passthrough, then ``duckdb.connect``.

Two things beyond opening are here because they are not in DuckDB's docs and each
was learned from a failure in production:

* :func:`is_lock_conflict` — a second process holding the write lock is reported
  as a generic ``IOException`` and is separable from a missing file or a
  permission error *only* by a substring of its message.
* :func:`rename_column` — DuckDB refuses ``ALTER TABLE … RENAME COLUMN`` while any
  secondary index exists on the table, so a migration must drop every index,
  rename, and rebuild them.

The README's "What this package knows" section records two further hazards that
have no code shape here — index churn and the static FTS index. Read it before
writing a sidecar's writer.

Schema, migrations and query surface stay with each store; this is deliberately
not a lifecycle base class.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb

# The stable substring in DuckDB's lock-contention message, verified against
# duckdb 1.x and pinned by a real two-process test:
#   IO Error: Could not set lock on file "...": Conflicting lock is held in ... (PID N) ...
_LOCK_CONFLICT_SIGNATURE = "Conflicting lock is held"

# `ON <table>(` — the start of an index's column list inside a CREATE INDEX
# statement, as `duckdb_indexes().sql` spells it back.
_INDEX_TARGET = re.compile(r"\bON\b\s+[^(]*\(", re.IGNORECASE)

# A single-quoted SQL string, doubled quotes included — the spans of an index
# expression that hold data rather than identifiers.
_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")


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


def is_lock_conflict(exc: BaseException) -> bool:
    """True iff ``exc`` is DuckDB's "another process holds the write lock" failure.

    DuckDB reports it as a plain :class:`duckdb.IOException`, the same class it
    uses for a missing file, an unreadable directory, or a corrupt header. The one
    thing that separates it is a substring of the message, so a caller that wants
    to say "something else is already writing this file" — and keep every other IO
    failure as its own real error — has to match that substring. Narrow by design:
    a non-``IOException`` never qualifies, whatever its message says.
    """
    return isinstance(exc, duckdb.IOException) and _LOCK_CONFLICT_SIGNATURE in str(exc)


def rename_column(conn: duckdb.DuckDBPyConnection, *, table: str, old: str, new: str) -> bool:
    """Rename ``old`` to ``new`` on ``table``, rebuilding the table's indexes around it.

    Returns True if the rename happened and False if there was nothing to rename,
    which is every database that never had ``old``: one already upgraded, one
    created fresh from current DDL, and one that took a different branch of a
    ladder where several old spellings converge on the same new name. Only a table
    holding *both* columns raises, because there the migration's own history is
    ambiguous and dropping one of them is not this function's call.

    **Why this is not one ``ALTER TABLE``.** DuckDB refuses to alter a table while
    anything depends on it, and a secondary index counts::

        duckdb.DependencyException: Cannot alter entry "node" because there are
        entries that depend on it.

    The message names neither the index nor the column, and a store usually meets
    it for the first time on a user's existing database — the one place iteration
    is not available. So every index on the table is dropped, the column is
    renamed, and each index is recreated from the definition DuckDB itself reports.
    An index over the renamed column has that column rewritten inside its own
    column list, and only there — a rename moves identifiers, so a single-quoted
    string that happens to spell the old name is left as the data it is.
    """
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({_quote(table)})").fetchall()}
    if old not in columns:
        return False
    if new in columns:
        msg = f"cannot rename {table}.{old} to {new}: {table}.{new} already exists"
        raise ValueError(msg)

    definitions = [
        _rewrite_index_columns(sql, old=old, new=new)
        for (sql,) in conn.execute(
            "SELECT sql FROM duckdb_indexes() WHERE table_name = ? ORDER BY index_name",
            [table],
        ).fetchall()
    ]
    for (index_name,) in conn.execute("SELECT index_name FROM duckdb_indexes() WHERE table_name = ?", [table]).fetchall():
        conn.execute(f"DROP INDEX {_quote(index_name)}")
    conn.execute(f"ALTER TABLE {_quote(table)} RENAME COLUMN {_quote(old)} TO {_quote(new)}")
    for definition in definitions:
        conn.execute(definition)
    return True


def _quote(identifier: str) -> str:
    """Quote an identifier for interpolation — DuckDB takes no parameter there."""
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def _rewrite_index_columns(sql: str, *, old: str, new: str) -> str:
    """Rewrite ``old`` to ``new`` inside a CREATE INDEX statement's column list only."""
    match = _INDEX_TARGET.search(sql)
    if match is None:
        return sql
    start = match.end()
    end = _closing_paren(sql, start)
    if end is None:
        return sql
    pattern = re.compile(rf"(?<![\w.]){re.escape(old)}(?![\w])")
    return sql[:start] + _sub_outside_strings(sql[start:end], pattern, new) + sql[end:]


def _sub_outside_strings(text: str, pattern: re.Pattern[str], new: str) -> str:
    """Apply `pattern` to `text`, skipping every single-quoted string in it."""
    pieces: list[str] = []
    position = 0
    for literal in _STRING_LITERAL.finditer(text):
        pieces.append(pattern.sub(new, text[position : literal.start()]))
        pieces.append(literal.group())
        position = literal.end()
    pieces.append(pattern.sub(new, text[position:]))
    return "".join(pieces)


def _closing_paren(sql: str, start: int) -> int | None:
    """Index of the ``)`` closing the group opened just before ``start``, or None.

    Parentheses inside a single-quoted string are data, so they do not count.
    """
    depth = 1
    index = start
    while index < len(sql):
        literal = _STRING_LITERAL.match(sql, index)
        if literal is not None:
            index = literal.end()
            continue
        depth += {"(": 1, ")": -1}.get(sql[index], 0)
        if depth == 0:
            return index
        index += 1
    return None


__all__ = ["connect", "is_lock_conflict", "rename_column"]
