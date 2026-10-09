"""A rotated JSON-lines log (moved from a2kay tests/services/test_audit_store.py: the
rotation, the in-process size count, reopen, torn line, read-only and append-only rules)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonl_log
import pytest
from jsonl_log import JsonlLog, LineError, LogClosedError, read, read_lines

_LIMIT = 1024


def _row(n: int) -> bytes:
    return json.dumps({"n": n}).encode()


def test_an_append_writes_one_line_and_flushes(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "log.jsonl"
    with JsonlLog.open(path) as log:
        assert log.append(_row(1))
        assert log.append(_row(2) + b"\n")  # a newline already there is not doubled
        assert path.read_bytes() == b'{"n": 1}\n{"n": 2}\n'  # flushed before close
    assert log.closed


def test_append_json_is_compact(tmp_path: Path) -> None:
    with JsonlLog.open(tmp_path / "log.jsonl") as log:
        log.append_json({"verb": "café", "n": 1})
    assert (tmp_path / "log.jsonl").read_text(encoding="utf-8") == '{"verb":"café","n":1}\n'


def test_a_line_with_an_inner_newline_is_refused(tmp_path: Path) -> None:
    with JsonlLog.open(tmp_path / "log.jsonl") as log, pytest.raises(LineError):
        log.append(b"one\ntwo")
    assert (tmp_path / "log.jsonl").read_bytes() == b""


def test_a_closed_log_refuses_an_append(tmp_path: Path) -> None:
    log = JsonlLog.open(tmp_path / "log.jsonl")
    log.close()
    with pytest.raises(LogClosedError) as caught:
        log.append(_row(1))
    assert caught.value.path == tmp_path / "log.jsonl"


def test_the_log_survives_a_reopen(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    with JsonlLog.open(path) as log:
        log.append(_row(1))
    with JsonlLog.open(path) as log:
        log.append(_row(2))
        assert [r["n"] for r in log.records(json.loads)] == [1, 2]


def test_a_full_file_rotates_and_the_oldest_is_dropped(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    path.write_bytes(b"x" * (_LIMIT - 4) + b"\n")
    for n in range(1, 5):
        path.with_name(f"log.jsonl.{n}").write_bytes(_row(n) + b"\n")

    with JsonlLog.open(path, rotate_bytes=_LIMIT, keep=5) as log:
        log.append(_row(99))

    assert path.read_bytes() == _row(99) + b"\n"
    assert path.with_name("log.jsonl.1").read_bytes().startswith(b"xxx")
    assert path.with_name("log.jsonl.4").read_bytes() == _row(3) + b"\n"
    assert not path.with_name("log.jsonl.5").exists()


def test_the_writer_counts_what_it_wrote(tmp_path: Path) -> None:
    """Rotation follows the in-process size count, seeded once at open; no file exceeds the limit."""
    path = tmp_path / "log.jsonl"
    line = b"y" * 99
    with JsonlLog.open(path, rotate_bytes=_LIMIT, keep=3) as log:
        for _ in range(40):
            log.append(line)
    files = [p for p in log.files() if p.exists()]
    assert len(files) == 3
    assert all(p.stat().st_size <= _LIMIT for p in files)
    assert sum(p.stat().st_size for p in files) % 100 == 0  # no line split across files


def test_keep_one_truncates_instead_of_shifting(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    with JsonlLog.open(path, rotate_bytes=16, keep=1) as log:
        log.append(b"a" * 10)
        log.append(b"b" * 10)
    assert path.read_bytes() == b"b" * 10 + b"\n"
    assert log.files() == [path]


def test_keep_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="keep"):
        JsonlLog(tmp_path / "log.jsonl", keep=0)


def test_reads_go_newest_file_first(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    path.with_name("log.jsonl.1").write_bytes(_row(1) + b"\n")
    with JsonlLog.open(path) as log:
        log.append(_row(2))
        assert [r["n"] for r in log.records(json.loads)] == [2, 1]


def test_a_torn_or_foreign_line_is_skipped(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    path.write_bytes(_row(1) + b"\n\n   \nnot json at all\n" + _row(2) + b'\n{"n": 3, "ver')
    assert list(read_lines(path)) == [_row(1), b"not json at all", _row(2), b'{"n": 3, "ver']
    assert [r["n"] for r in read(path, json.loads)] == [1, 2]


def test_no_log_yet_reads_empty(tmp_path: Path) -> None:
    with JsonlLog.open(tmp_path / "log.jsonl", read_only=True) as log:
        assert list(log.records(json.loads)) == []
    assert not (tmp_path / "log.jsonl").exists()


def test_a_read_only_log_appends_nothing(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    with JsonlLog.open(path) as writer:
        writer.append(_row(1))
        with JsonlLog.open(path, read_only=True) as reader:
            assert reader.read_only
            assert reader.append(_row(2)) is False
            assert [r["n"] for r in reader.records(json.loads)] == [1]
    assert path.read_bytes().count(b"\n") == 1


def test_the_module_only_appends() -> None:
    """No rewrite path exists: the log is opened in append mode only."""
    body = Path(jsonl_log.__file__).read_text(encoding="utf-8")
    assert '"ab"' in body
    for mode in ('"w"', '"wb"', '"r+"', '"r+b"', '"w+"'):
        assert f"open({mode}" not in body
        assert f", {mode})" not in body
    assert "write_text" not in body
    assert "write_bytes" not in body
