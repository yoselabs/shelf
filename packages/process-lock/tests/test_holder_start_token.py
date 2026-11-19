"""The holder record carries a start token, so a reused pid does not look like the holder (shelf-tyld.1).

Old lock files (bare pid, JSON without ``start``) keep parsing; the bytes written for the other keys do not change.
"""

from __future__ import annotations

import fcntl
import json
import os
from typing import TYPE_CHECKING

import pytest
import stream_proc
from process_lock import LockHeldError, ProcessLock, holder

if TYPE_CHECKING:
    from pathlib import Path


def _held_elsewhere(path: Path, body: bytes) -> int:
    """A second descriptor holds the flock (it conflicts even in-process) over a record we wrote."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    os.write(fd, body)
    return fd


def test_a_written_record_keeps_its_keys_in_order_and_ends_with_the_start_token(tmp_path: Path) -> None:
    token = stream_proc.proc_start(os.getpid())
    if token is None:
        pytest.skip("no process table on this OS")
    with ProcessLock.acquire(tmp_path / "a.lock", label="x", meta={"n": 1}) as lock:
        record = json.loads(lock.path.read_text(encoding="utf-8"))
    assert list(record) == ["pid", "created", "label", "meta", "start"]
    assert record["start"] == token
    assert (record["pid"], record["label"], record["meta"]) == (os.getpid(), "x", {"n": 1})


def test_an_old_record_without_a_start_token_still_parses(tmp_path: Path) -> None:
    path = tmp_path / "old.lock"
    path.write_text(json.dumps({"pid": 7, "created": 1.5, "label": "old", "meta": {}}), encoding="utf-8")
    parsed = holder(path)
    assert parsed is not None
    assert (parsed.pid, parsed.created, parsed.label, parsed.start) == (7, 1.5, "old", None)
    path.write_text("42", encoding="utf-8")  # v0.1 bare pid
    bare = holder(path)
    assert bare is not None
    assert (bare.pid, bare.start) == (42, None)


def test_a_live_pid_with_another_start_token_is_a_gone_holder(tmp_path: Path) -> None:
    """Pid reuse: the recorded pid is alive, but it began at another time, so it is not the holder."""
    if stream_proc.proc_start(os.getpid()) is None:
        pytest.skip("no process table on this OS")
    path = tmp_path / "reused.lock"
    fd = _held_elsewhere(path, json.dumps({"pid": os.getpid(), "created": 1.0, "start": "not-our-start"}).encode())
    try:
        with pytest.raises(LockHeldError) as caught:
            ProcessLock.acquire(path)
        assert str(caught.value).endswith(f"held by an inherited descriptor; recorded holder pid {os.getpid()} is gone")
    finally:
        os.close(fd)


def test_a_live_pid_with_its_own_start_token_is_a_live_holder(tmp_path: Path) -> None:
    token = stream_proc.proc_start(os.getpid())
    if token is None:
        pytest.skip("no process table on this OS")
    path = tmp_path / "live.lock"
    fd = _held_elsewhere(path, json.dumps({"pid": os.getpid(), "created": 1.0, "start": token}).encode())
    try:
        with pytest.raises(LockHeldError) as caught:
            ProcessLock.acquire(path)
        assert str(caught.value) == f"{path.resolve()} is locked by another process (pid {os.getpid()})"
    finally:
        os.close(fd)
