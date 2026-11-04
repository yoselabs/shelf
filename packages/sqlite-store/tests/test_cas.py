from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlite_store import cas_update

if TYPE_CHECKING:
    from pathlib import Path

    from sqlite_store import Store


def test_cas_conflicts_and_empty_update(tmp_path: Path, store: Store) -> None:
    con = store.shared_rw(tmp_path / "journal.db")
    assert con is not None
    con.execute("INSERT INTO item VALUES ('a', 'old', 0)")
    with store.begin_immediate(con):
        assert store.cas_update(con, "item", "id", "a", 0, value="new")
        assert not store.cas_update(con, "item", "id", "a", 0, value="stale")
        assert not store.cas_update(con, "item", "id", "absent", 0, value="missing")
        assert store.cas_update(con, "item", "id", "a", 1)
    assert con.execute("SELECT * FROM item").fetchall() == [("a", "new", 2)]


@pytest.mark.parametrize("table,cols", [("detail", {}), ("item", {"id": "b"})])
def test_cas_refuses_unrevisioned_and_identity_changes(tmp_path: Path, store: Store, table: str, cols: dict[str, str | int]) -> None:
    con = store.shared_rw(tmp_path / "journal.db")
    assert con is not None
    with store.begin_immediate(con), pytest.raises(ValueError, match="unrevisioned"):
        store.cas_update(con, table, "id", "a", 0, **cols)


def test_cas_requires_caller_transaction_and_quotes_identifiers(tmp_path: Path, store: Store) -> None:
    con = store.shared_rw(tmp_path / "journal.db")
    assert con is not None
    with pytest.raises(ValueError, match="caller-owned transaction"):
        store.cas_update(con, "item", "id", "a", 0, value="new")
    con.execute('CREATE TABLE "odd""table" ("key""col" TEXT, "value""col" TEXT, rev INTEGER)')
    con.execute("INSERT INTO \"odd\"\"table\" VALUES ('a', 'old', 0)")
    with store.begin_immediate(con):
        assert cas_update(con, 'odd"table', 'key"col', "a", 0, revisioned=frozenset({'odd"table'}), **{'value"col': "new"})
    assert con.execute('SELECT "value""col", rev FROM "odd""table"').fetchone() == ("new", 1)
