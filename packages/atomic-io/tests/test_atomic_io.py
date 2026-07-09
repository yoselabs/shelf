from __future__ import annotations

from pathlib import Path

import pytest
from atomic_io import atomic_write_text


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
