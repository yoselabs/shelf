"""SqliteResource lifecycle: lazy open, idempotent close, on_open hook, CM."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from sqlite_resource import SqliteResource

if TYPE_CHECKING:
    from pathlib import Path


async def _schema(conn) -> None:
    await conn.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)")


def test_no_io_until_ensure(tmp_path: Path) -> None:
    # Constructing the resource must not create the database file.
    db = tmp_path / "sub" / "data.sqlite"
    SqliteResource(db)
    assert not db.exists()
    assert not db.parent.exists()


async def test_ensure_opens_and_creates_parent(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "data.sqlite"
    res = SqliteResource(db, on_open=_schema)
    conn = await res.ensure()
    assert conn is res.conn
    assert db.exists()
    await res.conn.execute("INSERT INTO kv VALUES ('a', '1')")
    await res.conn.commit()
    await res.close()


async def test_ensure_is_idempotent(tmp_path: Path) -> None:
    res = SqliteResource(tmp_path / "d.sqlite")
    first = await res.ensure()
    second = await res.ensure()
    assert first is second
    await res.close()


async def test_conn_before_ensure_raises(tmp_path: Path) -> None:
    res = SqliteResource(tmp_path / "d.sqlite")
    with pytest.raises(RuntimeError, match="before ensure"):
        _ = res.conn


async def test_close_is_idempotent(tmp_path: Path) -> None:
    res = SqliteResource(tmp_path / "d.sqlite")
    await res.ensure()
    await res.close()
    await res.close()  # second close is a no-op
    with pytest.raises(RuntimeError):
        _ = res.conn


async def test_context_manager_opens_and_closes(tmp_path: Path) -> None:
    res = SqliteResource(tmp_path / "d.sqlite", on_open=_schema)
    async with res as entered:
        assert entered is res
        await res.conn.execute("INSERT INTO kv VALUES ('x', 'y')")
    with pytest.raises(RuntimeError):
        _ = res.conn


async def test_reentry_reopens(tmp_path: Path) -> None:
    db = tmp_path / "d.sqlite"
    res = SqliteResource(db, on_open=_schema)
    async with res:
        await res.conn.execute("INSERT INTO kv VALUES ('a', '1')")
        await res.conn.commit()
    async with res:
        async with res.conn.execute("SELECT v FROM kv WHERE k = 'a'") as cur:
            row = await cur.fetchone()
        assert row is not None
        assert row[0] == "1"


async def test_concurrent_first_callers_share_one_connection(tmp_path: Path) -> None:
    res = SqliteResource(tmp_path / "d.sqlite")
    conns = await asyncio.gather(*(res.ensure() for _ in range(8)))
    assert all(c is conns[0] for c in conns)
    await res.close()


async def test_custom_pragmas_applied(tmp_path: Path) -> None:
    res = SqliteResource(tmp_path / "d.sqlite", pragmas=("journal_mode=MEMORY",))
    await res.ensure()
    async with res.conn.execute("PRAGMA journal_mode") as cur:
        row = await cur.fetchone()
    assert row is not None
    assert row[0].lower() == "memory"
    await res.close()
