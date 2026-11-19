"""Connection-local change observations; transactions are sqlite-sidecar's ``transaction``."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3


def change_counter(con: sqlite3.Connection) -> int:
    """Compare successive data_version values on this connection only.

    Only another connection's commit changes the counter; counters from
    different connections cannot be compared.
    """
    return int(con.execute("PRAGMA data_version").fetchone()[0])
