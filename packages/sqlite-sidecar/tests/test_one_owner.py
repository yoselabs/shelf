"""One transaction, one error code, one move-aside (shelf-tyld.3), with golden stored names."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlite_sidecar as sc


def test_a_failed_commit_rolls_back_instead_of_leaving_the_transaction_open(tmp_path: Path) -> None:
    conn = sc.connect(tmp_path / "s.sqlite")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("CREATE TABLE parent(id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE child(p INTEGER REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED)")
    with pytest.raises(sqlite3.IntegrityError), sc.transaction(conn):
        conn.execute("INSERT INTO child VALUES (99)")  # the violation surfaces only at COMMIT
    assert not conn.in_transaction
    assert conn.execute("SELECT count(*) FROM child").fetchone() == (0,)
    conn.close()


def _busy_pair(path: Path) -> tuple[sqlite3.Connection, sqlite3.Connection]:
    """A rollback-journal file whose writer holds EXCLUSIVE, so any other open is busy."""
    holder = sqlite3.connect(path, isolation_level=None, timeout=0)
    holder.execute("CREATE TABLE t(x)")
    holder.execute("BEGIN EXCLUSIVE")
    return holder, sqlite3.connect(path, isolation_level=None, timeout=0)


def _coded(code: int, message: str) -> sqlite3.OperationalError:
    error = sqlite3.OperationalError(message)
    error.sqlite_errorcode = code
    return error


def test_is_busy_reads_the_error_code_not_the_message(tmp_path: Path) -> None:
    holder, other = _busy_pair(tmp_path / "s.sqlite")
    with pytest.raises(sqlite3.OperationalError) as busy:
        other.execute("SELECT * FROM t").fetchall()
    holder.execute("ROLLBACK")
    holder.close()
    other.close()
    assert sc.is_busy(busy.value)
    assert sc.is_busy(_coded(sqlite3.SQLITE_BUSY, "the file is occupied"))
    assert sc.is_busy(_coded(sqlite3.SQLITE_LOCKED, "table taken"))
    assert not sc.is_busy(sqlite3.OperationalError("database is locked"))  # words, no code
    assert not sc.is_busy(_coded(sqlite3.SQLITE_CORRUPT, "database is locked"))
    assert not sc.is_busy(ValueError("busy"))


def test_integrity_ok_raises_on_a_busy_file_instead_of_calling_it_damaged(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    holder, other = _busy_pair(path)
    other.close()
    try:
        with pytest.raises(sqlite3.OperationalError) as busy:
            sc.integrity_ok(path, timeout=0)
        assert sc.is_busy(busy.value)
    finally:
        holder.execute("ROLLBACK")
        holder.close()
    assert sc.integrity_ok(path)


def test_integrity_ok_is_false_for_damage_and_unknown_for_an_absent_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.sqlite"
    bad.write_bytes(b"x" * 4096)
    assert sc.integrity_ok(bad) is False
    with pytest.raises(sqlite3.OperationalError):
        sc.integrity_ok(tmp_path / "absent.sqlite")


def test_set_aside_moves_the_companions_before_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "graph.sqlite"
    for p in (db, tmp_path / "graph.sqlite-wal", tmp_path / "graph.sqlite-shm"):
        p.write_bytes(b"fictional")
    order: list[str] = []
    real = Path.replace

    def spy(self: Path, target: Path) -> Path:
        order.append(self.name)
        return real(self, target)

    monkeypatch.setattr(Path, "replace", spy)
    sc.set_aside(db, at=datetime(2026, 10, 2, 12, 0, tzinfo=UTC))
    assert order[-1] == "graph.sqlite", "a crash before the last move must never leave a WAL beside a fresh file"
    assert set(order) == {"graph.sqlite", "graph.sqlite-wal", "graph.sqlite-shm"}


def test_move_aside_names_each_destination_and_skips_what_is_absent(tmp_path: Path) -> None:
    db = tmp_path / "a.db"
    db.write_bytes(b"d")
    (tmp_path / "a.db-wal").write_bytes(b"w")
    moved = sc.move_aside(db, lambda src: src.with_name(src.name + ".old"))
    assert sorted(p.name for p in moved) == ["a.db-wal.old", "a.db.old"]
    assert (tmp_path / "a.db.old").read_bytes() == b"d"
    assert not (tmp_path / "a.db-shm.old").exists()


def test_golden_stored_names_and_schema_meta_do_not_change(tmp_path: Path) -> None:
    conn = sc.connect(tmp_path / "g.sqlite")
    sc.ensure_schema(conn, version=7, script="CREATE TABLE node (id TEXT);\n")
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'schema_meta'").fetchone()
    assert sql == ("CREATE TABLE schema_meta (schema_version INTEGER PRIMARY KEY)",)
    assert conn.execute("SELECT schema_version FROM schema_meta").fetchall() == [(7,)]
    conn.close()
    sc.mark_for_rebuild(tmp_path / "g.sqlite", reason="index drift")
    assert (tmp_path / "g.sqlite.rebuild").read_text(encoding="utf-8") == "index drift: rebuild before opening\n"
    assert sc.MARK_SUFFIX == ".rebuild"
