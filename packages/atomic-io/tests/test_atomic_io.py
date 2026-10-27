from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from atomic_io import atomic_write_bytes, atomic_write_json, atomic_write_text


def test_writes_full_content(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    atomic_write_text(target, "hello world")
    assert target.read_text(encoding="utf-8") == "hello world"


def test_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deep" / "note.txt"
    atomic_write_text(target, "x")
    assert target.read_text(encoding="utf-8") == "x"


def test_overwrites_existing_atomically(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    atomic_write_text(target, "v1")
    atomic_write_text(target, "v2")
    assert target.read_text(encoding="utf-8") == "v2"


def test_failed_replace_leaves_prior_intact_and_no_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "note.txt"
    atomic_write_text(target, "v1")

    def boom(_self: Path, _target: Path) -> None:
        msg = "replace interrupted"
        raise OSError(msg)

    monkeypatch.setattr(Path, "replace", boom)
    with pytest.raises(OSError, match="replace interrupted"):
        atomic_write_text(target, "v2")

    # prior content survives, and the temp file is cleaned up
    assert target.read_text(encoding="utf-8") == "v1"
    assert list(tmp_path.glob(".note.txt.*.tmp")) == []


def test_write_bytes_stores_exact_bytes(tmp_path: Path) -> None:
    target = tmp_path / "blob.bin"
    atomic_write_bytes(target, b"\x00\xff\r\n")
    assert target.read_bytes() == b"\x00\xff\r\n"


def test_write_json_options_and_trailing_newline(tmp_path: Path) -> None:
    target = tmp_path / "x.json"
    atomic_write_json(target, {"b": 1, "a": "é"}, indent=2, sort_keys=True)
    assert target.read_text(encoding="utf-8") == '{\n  "a": "é",\n  "b": 1\n}\n'


def test_fsync_is_skipped_on_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(os, "fsync", calls.append)
    atomic_write_bytes(tmp_path / "a", b"1", fsync=False)
    assert calls == []
    atomic_write_bytes(tmp_path / "b", b"1")
    assert len(calls) == 1


def test_keep_mode_without_a_prior_file_uses_the_umask_default(tmp_path: Path) -> None:
    old = os.umask(0o022)
    try:
        atomic_write_bytes(tmp_path / "new", b"1", keep_mode=True)
    finally:
        os.umask(old)
    assert stat.S_IMODE((tmp_path / "new").stat().st_mode) == 0o644
