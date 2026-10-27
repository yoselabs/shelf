"""jsonl_log.cursor — the byte-cursor reader and tail, beside the task-loop Jsonl it replaces."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from jsonl_log import Jsonl
from jsonl_log.cursor import CHUNK, read_from, tail

if TYPE_CHECKING:
    from pathlib import Path


def _text(line: bytes) -> str:
    return line.decode("utf-8")


def test_entries_carry_their_byte_span(tmp_path: Path) -> None:
    log = Jsonl(tmp_path / "a.jsonl")
    first = log.append({"n": 1})
    second = log.append({"n": 2})
    entries, cursor = log.read_from()
    assert [(e.start, e.end) for e in entries] == [(first, second), (second, log.size())]
    assert cursor == log.size()


def test_limit_stops_the_cursor_after_the_last_entry_returned(tmp_path: Path) -> None:
    log = Jsonl(tmp_path / "a.jsonl")
    for n in range(5):
        _ = log.append({"n": n})
    entries, cursor = log.read_from(limit=2)
    assert [e.data["n"] for e in entries] == [0, 1]
    rest, end = log.read_from(cursor)
    assert [e.data["n"] for e in rest] == [2, 3, 4]
    assert end == log.size()


def test_limit_reads_across_chunks(tmp_path: Path) -> None:
    log = Jsonl(tmp_path / "a.jsonl")
    for n in range(40):
        _ = log.append({"n": n, "pad": "x" * 5000})  # 200 KB: several chunks
    entries, _ = log.read_from(limit=30)
    assert [e.data["n"] for e in entries] == list(range(30))


def test_an_offset_past_the_end_restarts_from_zero(tmp_path: Path) -> None:
    log = Jsonl(tmp_path / "a.jsonl")
    _ = log.append({"n": 1})
    entries, _ = log.read_from(10_000)
    assert [e.data["n"] for e in entries] == [1]


def test_a_missing_file_keeps_the_cursor(tmp_path: Path) -> None:
    assert Jsonl(tmp_path / "none.jsonl").read_from(7) == ([], 7)
    assert Jsonl(tmp_path / "none.jsonl").tail(3) == []


def test_tail_returns_the_last_complete_entries_oldest_first(tmp_path: Path) -> None:
    log = Jsonl(tmp_path / "a.jsonl")
    for n in range(300):
        _ = log.append({"n": n, "pad": "y" * 400})  # well past one chunk
    assert [e.data["n"] for e in log.tail(3)] == [297, 298, 299]
    assert [e.data["n"] for e in log.tail(1000)][:2] == [0, 1]
    assert log.tail(0) == []
    assert log.size() > CHUNK


def test_tail_before_a_cursor_ignores_what_came_later(tmp_path: Path) -> None:
    log = Jsonl(tmp_path / "a.jsonl")
    _ = log.append({"n": 1})
    mark = log.size()
    _ = log.append({"n": 2})
    assert [e.data["n"] for e in log.tail(5, before=mark)] == [1]


def test_tail_skips_a_torn_last_line(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    path.write_bytes(b'{"n": 1}\n{"n"')
    assert [e.data["n"] for e in Jsonl(path).tail(5)] == [1]


def test_any_decoder_works_not_only_json_objects(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    path.write_bytes(b"alpha\nbeta\n\xff\xfe\ngamma")
    entries, cursor = read_from(path, _text)
    assert [e.data for e in entries] == ["alpha", "beta"]
    assert cursor == len(b"alpha\nbeta\n\xff\xfe\n")
    assert [e.data for e in tail(path, _text, 1)] == ["beta"]


def test_the_appended_line_is_plain_json(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    _ = Jsonl(path).append({"k": "é"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"k": "é"}
