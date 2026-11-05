"""Opt-in rotate_lock, rewrite and held handles: real processes, no line lost, no file dropped."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import threading
import time
from typing import TYPE_CHECKING

import jsonl_log
import pytest
from jsonl_log import JsonlLog, JsonlLogError, LogClosedError
from process_lock import ProcessLock

if TYPE_CHECKING:
    from pathlib import Path

_PAD = "x" * 100


def _tags(log: JsonlLog) -> list[tuple[str, int]]:
    return [(r["tag"], r["i"]) for r in log.records(json.loads)]


def _writer(path: str, tag: str, count: int, start: object) -> None:
    start.wait()  # type: ignore[attr-defined]
    with JsonlLog.open(path, rotate_bytes=2000, keep=1000, rotate_lock=True) as log:
        for i in range(count):
            log.append_json({"tag": tag, "i": i, "pad": _PAD})


def test_two_process_rotation_race_drops_no_line_and_no_file(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    ctx = mp.get_context("fork")
    start = ctx.Event()
    procs = [ctx.Process(target=_writer, args=(str(path), tag, 300, start)) for tag in "ab"]
    for p in procs:
        p.start()
    start.set()
    for p in procs:
        p.join(60)
        assert p.exitcode == 0
    with JsonlLog.open(path, keep=1000, read_only=True) as log:
        got = _tags(log)
        files = [f for f in log.files() if f.exists()]
    assert len(got) == len(set(got)) == 600  # every line, once
    assert len(files) > 5  # it did rotate, and kept every file (keep is far above)
    suffixes = sorted(int(f.suffix[1:]) for f in files if f != path)
    assert suffixes == list(range(1, len(suffixes) + 1))  # no gap: no file dropped


def test_without_the_lock_rotation_is_still_the_plain_one(tmp_path: Path) -> None:
    with JsonlLog.open(tmp_path / "l", rotate_bytes=50, keep=3) as log:
        for i in range(10):
            log.append_json({"i": i})
    assert (tmp_path / "l.1").exists()
    assert not (tmp_path / "l.lock").exists()


def test_a_rotator_that_waited_finds_the_file_already_rotated(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    lock = tmp_path / "log.jsonl.lock"
    with JsonlLog.open(path, rotate_bytes=100, keep=5, rotate_lock=True) as log:
        log.append(b"a" * 90)
        with ProcessLock.acquire(lock, reentrant=False):  # another rotator is mid-shift
            t = threading.Thread(target=lambda: log.append(b"c" * 20))  # needs a rotation: waits on the lock
            t.start()
            time.sleep(0.2)
            assert t.is_alive()
            path.replace(tmp_path / "log.jsonl.1")  # the other rotator finishes
            path.write_bytes(b"b\n")
        t.join(10)
    assert (tmp_path / "log.jsonl.1").read_bytes() == b"a" * 90 + b"\n"
    assert not (tmp_path / "log.jsonl.2").exists()  # the waiter did not shift again
    assert path.read_bytes() == b"b\n" + b"c" * 20 + b"\n"


def test_rewrite_keeps_what_is_accepted_and_counts_the_rest(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    with JsonlLog.open(path, rotate_lock=True) as log:
        for i in range(10):
            log.append_json({"i": i})
        dropped = log.rewrite(lambda line: json.loads(line)["i"] % 2 == 0)
        assert dropped == 5
        log.append_json({"i": 100})  # the log still appends, to the new file
        assert [r["i"] for r in log.records(json.loads)] == [0, 2, 4, 6, 8, 100]
        before = path.stat().st_ino
        assert log.rewrite(lambda _line: True) == 0
        assert path.stat().st_ino == before  # nothing dropped, nothing rewritten
    assert not path.with_name("log.jsonl.rewrite").exists()


def test_rewrite_needs_a_lock_and_a_writable_open_log(tmp_path: Path) -> None:
    with JsonlLog.open(tmp_path / "l") as log, pytest.raises(JsonlLogError):
        log.rewrite(lambda _l: True)
    log = JsonlLog.open(tmp_path / "m", rotate_lock=True)
    log.close()
    with pytest.raises(LogClosedError):
        log.rewrite(lambda _l: True)
    with JsonlLog.open(tmp_path / "m", rotate_lock=True, read_only=True) as ro:
        assert ro.rewrite(lambda _l: False) == 0
    assert JsonlLog.open(tmp_path / "absent", rotate_lock=True).rewrite(lambda _l: False) == 0


def test_rewrite_leaves_a_torn_last_line_and_blank_lines_alone(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    path.write_bytes(b'{"i":1}\n\n{"i":2}\n{"i":3')
    with JsonlLog.open(path, rotate_lock=True) as log:
        assert log.rewrite(lambda line: json.loads(line)["i"] == 2) == 1
    assert path.read_bytes() == b'{"i":2}\n{"i":3'


def _appender(path: str, count: int, locked: bool) -> None:
    with JsonlLog.open(path, rotate_lock=True) as log:
        for i in range(count):
            if locked:
                with log.locked():
                    log.append_json({"tag": "w", "i": i})
            else:
                log.append_json({"tag": "w", "i": i})


@pytest.mark.parametrize("locked", [False, True])
def test_rewrite_under_concurrent_appends_loses_no_kept_line(tmp_path: Path, locked: bool) -> None:
    path = tmp_path / "log.jsonl"
    with JsonlLog.open(path, rotate_lock=True) as log:
        for i in range(200):
            log.append_json({"tag": "old", "i": i})
        proc = mp.get_context("fork").Process(target=_appender, args=(str(path), 1500, locked))
        proc.start()
        dropped = 0
        while proc.is_alive():
            dropped += log.rewrite(lambda line: json.loads(line)["tag"] != "old")
        proc.join(30)
        assert proc.exitcode == 0
        dropped += log.rewrite(lambda line: json.loads(line)["tag"] != "old")
        rows = [(r["tag"], r["i"]) for r in log.records(json.loads)]
    assert dropped == 200
    assert sorted(rows) == [("w", i) for i in range(1500)]


def test_a_held_log_is_the_same_object_and_appends_correctly(tmp_path: Path) -> None:
    path = tmp_path / "h.jsonl"
    try:
        a = jsonl_log.held(path)
        assert jsonl_log.held(path) is a
        assert jsonl_log.held_count(path) == 1

        def work(n: int) -> None:
            for i in range(100):
                jsonl_log.held(path).append_json({"n": n, "i": i})

        threads = [threading.Thread(target=work, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        lines = path.read_bytes().splitlines()
        assert len(lines) == 400
        assert all(json.loads(line) for line in lines)
    finally:
        jsonl_log.close_held()
    assert jsonl_log.held_count() == 0
    assert a.closed


def test_a_held_log_follows_a_replaced_file_and_reopens_after_close(tmp_path: Path) -> None:
    path = tmp_path / "h.jsonl"
    try:
        jsonl_log.held(path).append(b"one")
        path.rename(tmp_path / "moved")
        jsonl_log.held(path).append(b"two")
        assert path.read_bytes() == b"two\n"
        jsonl_log.close_held(path)
        assert jsonl_log.held_count(path) == 0
        jsonl_log.held(path).append(b"three")
        assert path.read_bytes() == b"two\nthree\n"
    finally:
        jsonl_log.close_held()


def test_held_logs_are_bounded_and_the_oldest_closes_first(tmp_path: Path) -> None:
    from jsonl_log import _held  # noqa: PLC0415

    try:
        first = jsonl_log.held(tmp_path / "0")
        for n in range(1, _held.MAX_OPEN + 1):
            _ = jsonl_log.held(tmp_path / str(n))
        assert jsonl_log.held_count() == _held.MAX_OPEN
        assert first.closed
    finally:
        jsonl_log.close_held()


def _held_in_child(path: str, parent_log: JsonlLog) -> None:
    child = jsonl_log.held(path)
    child.append(b"child")
    os._exit(0 if child is not parent_log else 1)


def test_a_fork_child_opens_its_own_held_log(tmp_path: Path) -> None:
    path = tmp_path / "h.jsonl"
    try:
        parent = jsonl_log.held(path)
        parent.append(b"parent")
        proc = mp.get_context("fork").Process(target=_held_in_child, args=(str(path), parent))
        proc.start()
        proc.join(30)
        assert proc.exitcode == 0
        parent.append(b"parent2")
        assert sorted(path.read_bytes().splitlines()) == [b"child", b"parent", b"parent2"]
    finally:
        jsonl_log.close_held()
